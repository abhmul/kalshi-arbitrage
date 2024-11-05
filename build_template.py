"""
This code builds a template repository.
It should run without packages to allow for general use
before creating a virtual environment.
"""

import argparse
from pathlib import Path

parser = argparse.ArgumentParser()

ENVIRONMENT_YML = Path("environment.yml")
README = Path("README.md")


def replace_key(fname: Path, key: str, value: str):
    with open(fname, "r") as f:
        contents = f.read()
    replace_str = "{{" + key + "}}"
    assert replace_str in contents, f"Could not find {replace_str} in file {fname}."
    contents = contents.replace(replace_str, value)

    with open(fname, "w") as f:
        f.write(contents)


if __name__ == "__main__":
    # Just placeholder for when I add more complexity to this
    args = parser.parse_args()

    print("What title would you like to give the project?")
    project_title = input()
    replace_key(README, "PROJECT_TITLE", project_title)

    print("What name would like for your conda environment?")
    env_name = input()
    replace_key(ENVIRONMENT_YML, "ENV_NAME", env_name)

    print(
        f"""
        To complete installation please run the following commands:
        mamba env create -f environment.yml
        mamba activate {env_name}
        pip install -e .

        Or copy-paste this command to run them together:
        mamaba env create -f environment.yml && mamba activate {env_name} && pip install -e .
        """
    )
