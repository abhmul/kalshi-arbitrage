from typing import TypedDict, Sequence, Optional, Dict, Callable, Any
from inspect import signature
import numpy as np


class VectorizedInputReshapeOutput(TypedDict):
    to_vect: np.ndarray
    original_batch_shape: Sequence[int]
    was_batch: bool


def vectorized(
    arg_name: str | Sequence[str],
    row_ndim: int | Dict[str, int],
    output_names: Optional[Sequence[str]] = None,
):
    """
    A decorator that standardizes input into
    a vectorized function. The function is written
    as if the array comes in as a batch of inputs.
    This method will turn single samples into
    a batch of one input. It will then apply the function
    and extract the single output.

    In addition if the batch dimensions are multi-dimensional,
    it will flatten the batch dimensions, before applying
    the function. Then it will take the output of the function
    and reshape the batch dimensions to be their original size.

    This way, all vectorized functions have a standard shape
    of 1 batch dimension first, then `row_ndim` sample dimensions.

    Parameters
    ----------
    arg_name : str | Sequence[str]
        The name of the argument that the
        decorated function vectorizes. If passed a sequence,
        will vectorize all arguments. Expects them to have
        the same batch shapes.
    row_ndim : int | Dict[str, int]
        The number of dimensions of a single input that
        the function is vectorized over. The individual
        samples the function is vectorized over
        will be the last `row_ndim` axes of the array
        `arg_name`. If vectorizing over multiple arguments,
        pass a dictionary mapping each `arg_name` to the
        respective `row_ndim`.
    output_names : Optional[Sequence[str]]
        If passed, the function being vectorized will be
        treated as multi-output. In this case, it is expected
        to output a dictionary. The names passed to this argument
        tell @vectorized which of these outputs were vectorized
        by the function.
    """

    def reshape_res(
        res: np.ndarray, original_batch_shape: Sequence[int], was_batch: bool
    ):
        # Unflatten the batch dimensions
        res = res.reshape(*original_batch_shape, *res.shape[1:])

        # Remove the batch dimension if the input was a single sample
        if not was_batch:
            res = res[0]
        return res

    def reshape_input(
        to_vect: np.ndarray,
        row_ndim: int,
    ):
        # First introduct a batch dimension if the
        # input is a single value
        if row_ndim == 0:
            # Then either a value or an array
            was_batch = isinstance(to_vect, np.ndarray)
            if not was_batch:
                to_vect = np.array([to_vect])
        else:
            # It's an array, need to check the ndim
            was_batch = to_vect.ndim > row_ndim
            if not was_batch:
                to_vect = to_vect[None]
        assert to_vect.ndim > row_ndim

        # Now flatten the batch dimensions
        batch_ndim = to_vect.ndim - row_ndim
        original_batch_shape = to_vect.shape[:batch_ndim]
        original_row_shape = to_vect.shape[batch_ndim:]
        to_vect = to_vect.reshape(-1, *original_row_shape)

        return VectorizedInputReshapeOutput(
            to_vect=to_vect,
            original_batch_shape=original_batch_shape,
            was_batch=was_batch,
        )

    if isinstance(row_ndim, int):
        assert isinstance(arg_name, str)
        row_ndim = {arg_name: row_ndim}
    if isinstance(arg_name, str):
        arg_name = [arg_name]

    assert len(arg_name) > 0
    assert all(arg in row_ndim for arg in arg_name)

    def decorator(func: Callable[..., Any]):
        function_sig = signature(func)
        assert all(arg in function_sig.parameters for arg in arg_name)
        assert all(ndim >= 0 for ndim in row_ndim.values())
        func.vectorized_argument = arg_name  # type: ignore[attr-defined]
        func.row_ndim = row_ndim  # type: ignore[attr-defined]

        def vectorized_func(*args, **kwargs):
            bound_sig = function_sig.bind(*args, **kwargs)

            reshape_input_results: Dict[str, VectorizedInputReshapeOutput] = {}
            for arg in arg_name:
                to_vect = bound_sig.arguments[arg]

                reshape_input_result = reshape_input(
                    to_vect=to_vect, row_ndim=row_ndim[arg]
                )
                reshape_input_results[arg] = reshape_input_result

            # Check that everything looks good in the arguments
            original_batch_shape = reshape_input_results[arg_name[0]][
                "original_batch_shape"
            ]
            was_batch = reshape_input_results[arg_name[0]]["was_batch"]
            assert all(
                original_batch_shape
                == reshape_input_results[arg]["original_batch_shape"]
                for arg in arg_name
            )
            assert all(
                was_batch == reshape_input_results[arg]["was_batch"] for arg in arg_name
            )

            # Update the function signature arguments
            for arg in arg_name:
                bound_sig.arguments[arg] = reshape_input_results[arg]["to_vect"]
            res = func(**bound_sig.arguments)

            if output_names is None:
                # Assuming single output
                res = reshape_res(
                    res=res,
                    original_batch_shape=original_batch_shape,
                    was_batch=was_batch,
                )

            else:
                new_res = {}
                for oname in output_names:
                    new_res[oname] = reshape_res(
                        res=res[oname],
                        original_batch_shape=original_batch_shape,
                        was_batch=was_batch,
                    )
                res = new_res

            return res

        return vectorized_func

    return decorator


def concatenate_broadcast(arrs: Sequence[np.ndarray], axis: int = -1):
    ndim = arrs[0].ndim
    assert all(ndim == a.ndim for a in arrs)

    if axis < 0:
        axis_lb = ndim + axis
        axis_ub = ndim + axis + 1
    else:
        axis_lb = axis
        axis_ub = axis + 1
    shapes = [arr.shape[:axis_lb] + arr.shape[axis_ub:] for arr in arrs]

    broadcast_shape = np.broadcast_shapes(*shapes)
    arrs = [
        np.broadcast_to(
            a, (*broadcast_shape[:axis_lb], a.shape[axis], *broadcast_shape[axis_lb:])
        )
        for a in arrs
    ]

    return np.concatenate(arrs, axis=axis)


def stack_broadcast(arrs: Sequence[np.ndarray], axis: int = -1):
    return concatenate_broadcast([np.expand_dims(a, axis) for a in arrs], axis=axis)
