# TODO

## Basic Design Ideas

### Server/Client Setup

1. Code up a server that different clients can interact with for trading and querying Kalshi. Basically a go-between.
   - Different clients run different strategies.
   - Server does appropriate rate-limiting. Also tries to minimize number of calls to the API it needs to do.
   - Clients should register their strategy with the server. Server should persist necessary details that can be reloaded if the client logs off, then turns back on. Also if the server shuts down. This will be important early on because I won't have it setup to be constantly running. At some point I'll move to AWS and will want to use spot-instances to keep costs down. So things need to be able to save and reload state.
2. Code can be setup with package for
   - server
   - client
   - and shared libraries

### Model Training and Forecasting

1. Need to collect data for different strategies. I can start with temperature betting.
   - [ ] Download historical NWS data climate data for the different cities on Kalshi.
   - [ ] Download historical NWS forecast data at hour increments.
2. Data Analysis
   - [ ] Plot distribution of differential between forecast and actual outcome for different cities.
   - [ ] Work out appropriate betting strategies that maximize expected profit, but minimize variance.
   - [ ] Train LR model on input forecast data
