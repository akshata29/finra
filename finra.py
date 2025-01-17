import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from io import StringIO
from datetime import datetime, timedelta
import requests
import yfinance as yf
from plotly.subplots import make_subplots

# Directory for local data storage
DATA_DIR = "Data/Finra"
os.makedirs(DATA_DIR, exist_ok=True)
st.set_page_config(layout="wide")


# Function to download FINRA data for a specific date
def download_finra_data(date):
    base_url = "https://cdn.finra.org/equity/regsho/daily/"
    filename = f"CNMSshvol{date.strftime('%Y%m%d')}.txt"
    file_path = os.path.join(DATA_DIR, filename)
    if os.path.exists(file_path):
        return pd.read_csv(file_path, sep='|')

    url = base_url + filename
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(file_path, 'w') as f:
            f.write(response.text)
        data = pd.read_csv(StringIO(response.text), sep='|')
        return data
    except requests.exceptions.RequestException as e:
        #st.warning(f"Error downloading data for {date}: {e}")
        return None

# Function to get data for a specific date
def get_data_for_date(date):
    return download_finra_data(date)

# Function to fetch closing prices from Yahoo Finance
def fetch_closing_prices(symbols):
    prices = {}
    for symbol in symbols:
        try:
            stock = yf.Ticker(symbol)
            history = stock.history(period="1d")
            if not history.empty:
                prices[symbol] = history["Close"].iloc[0]
        except Exception as e:
            st.warning(f"Could not fetch price for {symbol}: {e}")
    return prices

# Helper function to plot average DP Index
def plot_dpindex(data):
    data['Date'] = pd.to_datetime(data['Date'])
    data = data.sort_values(by='Date')

    # Calculate averages over timeframes
    data['DP Index 5D'] = data['DP Index'].rolling(window=5).mean()
    data['DP Index 2W'] = data['DP Index'].rolling(window=10).mean()
    data['DP Index 1M'] = data['DP Index'].rolling(window=20).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data['Date'], y=data['DP Index 5D'], mode='lines', name='5-Day Avg'))
    fig.add_trace(go.Scatter(x=data['Date'], y=data['DP Index 2W'], mode='lines', name='2-Week Avg'))
    fig.add_trace(go.Scatter(x=data['Date'], y=data['DP Index 1M'], mode='lines', name='1-Month Avg'))

    fig.update_layout(
        title="Average DP Index Over Time",
        xaxis_title="Date",
        yaxis_title="DP Index",
        legend_title="Timeframe",
        template="plotly_white"
    )

    st.plotly_chart(fig)

# Helper function to plot average DP Index and Closing Price in two panels
def plot_dpindex_and_price(data, symbol):
    data['Date'] = pd.to_datetime(data['Date'])
    data = data.sort_values(by='Date')

    # Calculate averages over timeframes
    data['DP Index'] = data['DP Index']
    data['DP Index 5D'] = data['DP Index'].rolling(window=5).mean()
    data['DP Index 2W'] = data['DP Index'].rolling(window=10).mean()
    data['DP Index 1M'] = data['DP Index'].rolling(window=20).mean()

    # Fetch closing prices for the symbol
    stock = yf.Ticker(symbol)
    price_data = stock.history(start=data['Date'].min(), end=data['Date'].max())
    if not price_data.empty:
        price_data = price_data.reset_index()
        price_data['Date'] = price_data['Date'].dt.date

        # Create subplots with two panels
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=("Closing Price", "DP Index Averages")
        )

        # Add closing price to the top panel
        fig.add_trace(
            go.Scatter(x=price_data['Date'], y=price_data['Close'], mode='lines', name='Closing Price'),
            row=1, col=1
        )

        # Add DP Index averages to the bottom panel
        fig.add_trace(
            go.Scatter(x=data['Date'], y=data['DP Index'], mode='lines', name='DP Index'),
            row=2, col=1
        )
        fig.add_trace(
            go.Scatter(x=data['Date'], y=data['DP Index 5D'], mode='lines', name='5-Day Avg DP Index'),
            row=2, col=1
        )
        fig.add_trace(
            go.Scatter(x=data['Date'], y=data['DP Index 2W'], mode='lines', name='2-Week Avg DP Index'),
            row=2, col=1
        )
        fig.add_trace(
            go.Scatter(x=data['Date'], y=data['DP Index 1M'], mode='lines', name='1-Month Avg DP Index'),
            row=2, col=1
        )

        # Update layout
        fig.update_layout(
            title=f"Closing Price and DP Index Averages for {symbol}",
            xaxis_title="Date",
            yaxis_title="Closing Price",
            yaxis2_title="DP Index",
            template="plotly_white"
        )

        st.plotly_chart(fig)


# Streamlit UI
st.title("Dark Volume Dashboard")

# Tabs for different features
tabs = st.tabs(["Ticker Analysis", "Top Dark Pools", "Volume Buy/Sell Analysis", "Buy Signal Analysis", "Accumulation", "Filter Analysis", "Accumulation Analysis"])

# Ticker Analysis Tab
with tabs[0]:
    st.header("Ticker Analysis")

    # Inputs
    symbol = st.text_input("Enter the symbol (e.g., SPY):", value="SPY").strip().upper()
    end_date = st.date_input("End Date:", value=datetime.today(), key="end_date")
    start_date = end_date - timedelta(days=180)

    if st.button("Run Ticker Analysis"):
        # Adjust end_date for market close data availability
        if datetime.now().time() < datetime.strptime("17:00", "%H:%M").time():
            end_date = end_date - timedelta(days=1)

        # Filter out weekends
        dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        dates = [date for date in dates if date.weekday() < 5]  # Exclude weekends

        data_frames = []
        for date in dates:
            daily_data = get_data_for_date(date)
            if daily_data is not None:
                daily_data = daily_data[daily_data['Symbol'] == symbol]
                if not daily_data.empty:
                    daily_data['Date'] = date
                    data_frames.append(daily_data)

        if data_frames:
            data = pd.concat(data_frames, ignore_index=True)

            # Process data
            data['Bought'] = data['ShortVolume']  # Assuming ShortVolume as Bought
            data['Sold'] = data['TotalVolume'] - data['ShortVolume']
            data['Total Volume'] = data['Bought'] + data['Sold']
            data['Buy-Sell Ratio'] = data['Bought'] / data['Sold']
            data['% Avg'] = data['Total Volume'] / data['Total Volume'].mean() * 100
            data['DP Index'] = (data['Bought'] / data['Total Volume'] * 100).round(2)

            # Format Date
            data['Date'] = pd.to_datetime(data['Date']).dt.strftime('%Y-%m-%d')

            # Identify accumulation patterns
            data['Accumulation'] = data['Buy-Sell Ratio'] > 1.25
            data['Rolling Accumulation'] = data['Accumulation'].rolling(window=5, min_periods=5).sum() >= 5

            accumulation_dates = data.loc[data['Rolling Accumulation'], 'Date'].tolist()

            if accumulation_dates:
                st.markdown("### **Accumulation Detected**")
                st.markdown(f"The following dates show consistent accumulation over the period:")
                for date in accumulation_dates:
                    st.markdown(f"- **{date}**")
            else:
                st.markdown("### **No Accumulation Detected**")

            # Cumulative calculations
            #data['Cumulative Buying'] = data['Bought'].cumsum()
            #data['Cumulative Selling'] = data['Sold'].cumsum()
            data['Cumulative Buying'] = data['Bought'].rolling(window=2, min_periods=1).sum()
            data['Cumulative Selling'] = data['Sold'].rolling(window=2, min_periods=1).sum()

            # Plot DP Index averages
            st.write("### DP Index Averages Over Time")
            plot_dpindex_and_price(data, symbol)
            
            # Color coding
            def highlight_row(row):
                if row['Bought'] > row['Sold']:
                    return ["background-color: yellow"] + ["background-color: lightgreen"] * 8 + ["background-color: lightgreen"]
                else:
                    return ["background-color: yellow"] + ["background-color: lightcoral"] * 8 + ["background-color: lightcoral"]

            # Filter the data to show last 30 days in descending order
            data = data.sort_values(by='Date', ascending=False).head(30)

            # Create summary table
            table_data = data[['Date', 'Symbol', 'Bought', 'Sold', '% Avg', 'Buy-Sell Ratio', 'DP Index', 'Total Volume', 'Cumulative Buying', 'Cumulative Selling']]
            styled_table = table_data.style.apply(highlight_row, axis=1)
            st.write("### Dark Volume Table")
            st.dataframe(styled_table.format(precision=2), use_container_width=True)

            # Summary statistics
            total_volume = data['Total Volume'].sum()
            total_bought = data['Bought'].sum()
            total_sold = data['Sold'].sum()
            avg_total_volume = data['Total Volume'].mean()
            avg_buy_sell_ratio = data['Buy-Sell Ratio'].mean()
            avg_buy_volume = data['Bought'].mean()
            avg_sell_volume = data['Sold'].mean()

            # Display summary
            st.write("### Summary Statistics")
            st.markdown(f"""
            - **Total Volume:** {total_volume:,}
            - **Total Bought:** {total_bought:,}
            - **Total Sold:** {total_sold:,}
            - **Average Total Volume:** {avg_total_volume:,.2f}
            - **Average Buy-Sell Ratio:** {avg_buy_sell_ratio:,.2f}
            - **Average Buy Volume:** {avg_buy_volume:,.2f}
            - **Average Sell Volume:** {avg_sell_volume:,.2f}
            """)
        else:
            st.warning("No data available for the selected range and symbol.")

# Top Dark Pools Tab
with tabs[1]:
    st.header("Top Dark Pools")
    st.subheader("Analyse the top dark pools with on a specific date with a specific volume and price threshold.  It analyses the top dark pools with consistent accumulation patterns and high buy-sell ratios.")

    # Inputs
    analysis_end_date = st.date_input("End Date for Analysis:", value=datetime.today())
    min_volume = st.number_input("Minimum Volume (Bought and Sold):", value=1_000_000, step=100_000)
    analysis_start_date = analysis_end_date - timedelta(days=14)
    price_threshold = st.number_input("Price Threshold (Default $10):", value=5.0, step=1.0)

    if st.button("Run Dark Pools Analysis"):
        # Adjust end_date for market close data availability
        base_url = "https://cdn.finra.org/equity/regsho/daily/"
        filename = f"CNMSshvol{analysis_end_date.strftime('%Y%m%d')}.txt"
        file_path = os.path.join(DATA_DIR, filename)
        if os.path.exists(file_path):
        #if datetime.now().time() < datetime.strptime("17:00", "%H:%M").time():
            analysis_end_date = analysis_end_date
        else:
            analysis_end_date = analysis_end_date - timedelta(days=1)

        # Filter out weekends
        dates = [analysis_start_date + timedelta(days=i) for i in range((analysis_end_date - analysis_start_date).days + 1)]
        dates = [date for date in dates if date.weekday() < 5]  # Exclude weekends

        data_frames = []
        for date in dates:
            daily_data = get_data_for_date(date)
            if daily_data is not None:
                daily_data['Bought'] = daily_data['ShortVolume']  # Assuming ShortVolume as Bought
                daily_data['Sold'] = daily_data['TotalVolume'] - daily_data['ShortVolume']
                daily_data = daily_data[(daily_data['Bought'] >= min_volume) & (daily_data['Sold'] >= min_volume)]
                daily_data['Date'] = date
                data_frames.append(daily_data)

        if data_frames:
            combined_data = pd.concat(data_frames, ignore_index=True)

            # Process data
            combined_data['Total Volume'] = combined_data['Bought'] + combined_data['Sold']
            combined_data['Buy-Sell Ratio'] = combined_data['Bought'] / combined_data['Sold']
            combined_data['% Avg'] = combined_data['TotalVolume'] / combined_data['TotalVolume'].mean() * 100
            combined_data['DP Index'] = (combined_data['Bought'] / combined_data['TotalVolume'] * 100).round(2)

            # Format Date
            combined_data['Date'] = pd.to_datetime(combined_data['Date']).dt.strftime('%Y-%m-%d')

            # Identify accumulation patterns
            accumulation = combined_data.groupby(['Symbol', 'Date']).agg({
                'Buy-Sell Ratio': 'mean',
                'Bought': 'sum',
                'Sold': 'sum'
            }).reset_index()

            accumulation['Consistent Accumulation'] = accumulation.groupby('Symbol')['Buy-Sell Ratio'].transform(
                lambda x: (x > 1.25).rolling(window=5, min_periods=5).sum() >= 5
            )

            # Filter for consistent accumulation
            accumulation = accumulation[accumulation['Consistent Accumulation']]

            # Aggregate and sort to find top dark pools
            top_dark_pools = accumulation.groupby('Symbol').agg({
                'Bought': 'sum',
                'Sold': 'sum',
                'Buy-Sell Ratio': 'mean'
            }).reset_index()

            top_dark_pools = top_dark_pools.sort_values(by=['Buy-Sell Ratio'], ascending=False).head(100)

	    # Fetch closing prices and filter by price threshold
            unique_symbols = top_dark_pools['Symbol'].unique()
            closing_prices = fetch_closing_prices(unique_symbols)
            top_dark_pools['Closing Price'] = top_dark_pools['Symbol'].map(closing_prices)
            top_dark_pools = top_dark_pools[top_dark_pools['Closing Price'] > price_threshold]
            top_dark_pools['Date'] = analysis_end_date

            # Create summary table
            st.write("### Top 10 Dark Pools with Accumulation")
            st.dataframe(top_dark_pools[['Date', 'Symbol', 'Closing Price', 'Bought', 'Sold', 'Buy-Sell Ratio']], use_container_width=True)

            # Summary statistics
            total_volume = top_dark_pools['Bought'].sum() + top_dark_pools['Sold'].sum()
            total_bought = top_dark_pools['Bought'].sum()
            total_sold = top_dark_pools['Sold'].sum()
            avg_buy_sell_ratio = top_dark_pools['Buy-Sell Ratio'].mean()

            # Display summary
            st.write("### Summary Statistics for Top 10 Dark Pools")
            st.markdown(f"""
            - **Total Volume:** {total_volume:,}
            - **Total Bought:** {total_bought:,}
            - **Total Sold:** {total_sold:,}
            - **Average Buy-Sell Ratio:** {avg_buy_sell_ratio:,.2f}
            """)
        else:
            st.warning("No data available for the selected range.")

with tabs[2]:
    st.header("Volume Buy/Sell Analysis")
    st.subheader("Analyse the top stocks by volume bought and sold on a specific date. It analyses the top stocks with high buy-sell ratios and DP Index values.")
    analysis_date = st.date_input("Select Date for Top Volume Analysis:", value=datetime.today())
    min_volume = st.number_input("Minimum Volume (Bought and Sold):", value=1_000_000, step=100_000, key="min_volume_vol")
    price_threshold = st.number_input("Price Threshold (Default $10):", value=5.0, step=1.0, key="price_threshold_vol")

    if st.button("Buy Volume Analysis"):
        # Use provided date for analysis
        # if datetime.now().time() < datetime.strptime("17:00", "%H:%M").time() and analysis_date == datetime.today():
        #     analysis_date = analysis_date - timedelta(days=1)
        base_url = "https://cdn.finra.org/equity/regsho/daily/"
        filename = f"CNMSshvol{analysis_end_date.strftime('%Y%m%d')}.txt"
        file_path = os.path.join(DATA_DIR, filename)
        if os.path.exists(file_path):
        #if datetime.now().time() < datetime.strptime("17:00", "%H:%M").time():
            analysis_date = analysis_date
        else:
            analysis_date = analysis_date - timedelta(days=1)

        # Get data for the selected date
        daily_data = get_data_for_date(analysis_date)

        if daily_data is not None:
            # Process data
            daily_data['Bought'] = daily_data['ShortVolume']  # Assuming ShortVolume as Bought
            daily_data['Sold'] = daily_data['TotalVolume'] - daily_data['ShortVolume']
            daily_data['Total Volume'] = daily_data['Bought'] + daily_data['Sold']
            daily_data['Buy-Sell Ratio'] = daily_data['Bought'] / daily_data['Sold']
            daily_data['% Avg'] = daily_data['TotalVolume'] / daily_data['TotalVolume'].mean() * 100
            daily_data['DP Index'] = (daily_data['Bought'] / daily_data['TotalVolume'] * 100).round(2)

            daily_data = daily_data[(daily_data['Bought'] >= min_volume) & (daily_data['Sold'] >= min_volume)]
            # Format Date
            #daily_data['Date'] = pd.to_datetime(daily_data['Date']).dt.strftime('%Y-%m-%d')
            daily_data = daily_data[daily_data['Buy-Sell Ratio'] > 1.5]

            # Add BTD Tag logic
            daily_data['BTD Tag'] = (daily_data['Buy-Sell Ratio'] > 1.5 ) & (daily_data['DP Index'] > 50)

            # Sort by Buy-Sell Ratio, DP Index and Bought Volume
            top_volume_stocks = daily_data.sort_values(by=['Buy-Sell Ratio', 'DP Index', 'Bought'], ascending=False).head(100)
            # Convert the data type of the 'Date' column to string
            top_volume_stocks['Date'] = top_volume_stocks['Date'].astype(str)
            top_volume_stocks['Date'] = pd.to_datetime(top_volume_stocks['Date']).dt.strftime('%Y-%m-%d')

	    # Fetch closing prices and filter by price threshold
            unique_symbols = top_volume_stocks['Symbol'].unique()
            closing_prices = fetch_closing_prices(unique_symbols)
            top_volume_stocks['Closing Price'] = top_volume_stocks['Symbol'].map(closing_prices)
            top_volume_stocks = top_volume_stocks[top_volume_stocks['Closing Price'] > price_threshold]


            # Create summary table
            st.write("### Top 10 Stocks by Volume Bought")
            st.dataframe(top_volume_stocks[['Date', 'Symbol', 'Closing Price', 'Bought',  'Sold', 'Buy-Sell Ratio', 'DP Index', 'Total Volume', 'BTD Tag']], use_container_width=True)
        else:
            st.warning("No data available for the selected date.")
    if st.button("Sell Volume Analysis"):
        # Use provided date for analysis
        # if datetime.now().time() < datetime.strptime("17:00", "%H:%M").time() and analysis_date == datetime.today():
        #     analysis_date = analysis_date - timedelta(days=1)
        base_url = "https://cdn.finra.org/equity/regsho/daily/"
        filename = f"CNMSshvol{analysis_end_date.strftime('%Y%m%d')}.txt"
        file_path = os.path.join(DATA_DIR, filename)
        if os.path.exists(file_path):
        #if datetime.now().time() < datetime.strptime("17:00", "%H:%M").time():
            analysis_date = analysis_date
        else:
            analysis_date = analysis_date - timedelta(days=1)

        # Get data for the selected date
        daily_data = get_data_for_date(analysis_date)

        if daily_data is not None:
            # Process data
            daily_data['Bought'] = daily_data['ShortVolume']  # Assuming ShortVolume as Bought
            daily_data['Sold'] = daily_data['TotalVolume'] - daily_data['ShortVolume']
            daily_data['Total Volume'] = daily_data['Bought'] + daily_data['Sold']
            daily_data['Buy-Sell Ratio'] = daily_data['Bought'] / daily_data['Sold']
            daily_data['% Avg'] = daily_data['TotalVolume'] / daily_data['TotalVolume'].mean() * 100
            daily_data['DP Index'] = (daily_data['Bought'] / daily_data['TotalVolume'] * 100).round(2)
            daily_data = daily_data[(daily_data['Bought'] >= min_volume) & (daily_data['Sold'] >= min_volume)]

            # Format Date
            #daily_data['Date'] = pd.to_datetime(daily_data['Date']).dt.strftime('%Y-%m-%d')

            # Filter to display only stocks with Buy-Sell Ratio < 0.5
            daily_data = daily_data[daily_data['Buy-Sell Ratio'] < 0.5]

            # Add BTD Tag logic
            daily_data['BTD Tag'] = (daily_data['Buy-Sell Ratio'] < 0.5) & (daily_data['DP Index'] < 47)

            # Sort by Bought Volume
            top_volume_stocks1 = daily_data.sort_values(by=['Buy-Sell Ratio', 'DP Index', 'Sold'], ascending=False).head(100)
            # Convert the data type of the 'Date' column to string
            top_volume_stocks1['Date'] = top_volume_stocks1['Date'].astype(str)
            top_volume_stocks1['Date'] = pd.to_datetime(top_volume_stocks1['Date']).dt.strftime('%Y-%m-%d')

	    # Fetch closing prices and filter by price threshold
            unique_symbols = top_volume_stocks1['Symbol'].unique()
            closing_prices = fetch_closing_prices(unique_symbols)
            top_volume_stocks1['Closing Price'] = top_volume_stocks1['Symbol'].map(closing_prices)
            top_volume_stocks1 = top_volume_stocks1[top_volume_stocks1['Closing Price'] > price_threshold]


            # Create summary table
            st.write("### Top 10 Stocks by Volume Sold")
            st.dataframe(top_volume_stocks1[['Date', 'Symbol', 'Bought', 'Sold', 'Buy-Sell Ratio', 'DP Index', 'Total Volume', 'BTD Tag']], use_container_width=True)
        else:
            st.warning("No data available for the selected date.")

# Add a new tab for Buy Signal Analysis
with tabs[3]:
    st.header("Buy Signal Analysis")
    st.subheader("Analyse the top stocks with buy signals on a specific date. It analyses the top stocks with high buy-sell ratios and DP Index values.  The DP Index values are looked across multiple averages (5, 2 Week and 1 Month)")
    # Inputs
    analysis_end_date = st.date_input("End Date for Buy Signal Analysis:", value=datetime.today(), key="buy_signal_end_date")
    analysis_start_date = analysis_end_date - timedelta(days=90)
    signal_start_date = analysis_date - timedelta(days=1)
    min_volume = st.number_input("Minimum Volume (Bought and Sold):", value=1_000_000, step=100_000, key="min_volume")
    price_threshold = st.number_input("Price Threshold (Default $10):", value=5.0, step=1.0, key="price_threshold")


    if st.button("Run Buy Signal Analysis"):
        # Adjust end_date for market close data availability
        # if datetime.now().time() < datetime.strptime("17:00", "%H:%M").time():
        #     analysis_end_date = analysis_end_date - timedelta(days=1)
        base_url = "https://cdn.finra.org/equity/regsho/daily/"
        filename = f"CNMSshvol{analysis_end_date.strftime('%Y%m%d')}.txt"
        file_path = os.path.join(DATA_DIR, filename)
        if os.path.exists(file_path):
            analysis_end_date = analysis_end_date
        else:
            analysis_end_date = analysis_end_date - timedelta(days=1)

        # Filter out weekends
        dates = [analysis_start_date + timedelta(days=i) for i in range((analysis_end_date - analysis_start_date).days + 1)]
        dates = [date for date in dates if date.weekday() < 5]  # Exclude weekends

        data_frames = []
        for date in dates:
            daily_data = get_data_for_date(date)
            if daily_data is not None:
                daily_data['Date'] = date
                data_frames.append(daily_data)

        if data_frames:
            combined_data = pd.concat(data_frames, ignore_index=True)

            # Process data
            combined_data['Bought'] = combined_data['ShortVolume']  # Assuming ShortVolume as Bought
            combined_data['Sold'] = combined_data['TotalVolume'] - combined_data['ShortVolume']
            combined_data['Total Volume'] = combined_data['Bought'] + combined_data['Sold']
            combined_data['Buy-Sell Ratio'] = combined_data['Bought'] / combined_data['Sold']
            combined_data['% Avg'] = combined_data['TotalVolume'] / combined_data['TotalVolume'].mean() * 100
            combined_data['DP Index'] = (combined_data['Bought'] / combined_data['Total Volume'] * 100).round(2)
            combined_data['DP Index 5D'] = combined_data.groupby('Symbol')['DP Index'].transform(lambda x: x.rolling(window=5).mean())
            combined_data['DP Index 2W'] = combined_data.groupby('Symbol')['DP Index'].transform(lambda x: x.rolling(window=10).mean())
            combined_data['DP Index 1M'] = combined_data.groupby('Symbol')['DP Index'].transform(lambda x: x.rolling(window=20).mean())

            combined_data = combined_data[(combined_data['Bought'] >= min_volume) & (combined_data['Sold'] >= min_volume)]

            # Generate Buy Signals
            buy_signals = combined_data[
                (combined_data['DP Index'] > 50) &
                (combined_data['DP Index 5D'] > 50) &
                (combined_data['DP Index 2W'] > 50) &
                (combined_data['DP Index 1M'] > 50) &
                (combined_data['Buy-Sell Ratio'] > 1.25) &
                (combined_data['% Avg'] > 100)
            ]

            # Make sure we are displaying the signals for the selected date range
            buy_signals = buy_signals[(buy_signals['Date'] >= signal_start_date) & (buy_signals['Date'] <= analysis_end_date
            )]

            unique_symbols = buy_signals['Symbol'].unique()
            closing_prices = fetch_closing_prices(unique_symbols)
            buy_signals['Closing Price'] = buy_signals['Symbol'].map(closing_prices)
            buy_signals = buy_signals[buy_signals['Closing Price'] > price_threshold]

      
            # sort the dataframe by Bought Volume, Buy-Sell Ratio, and DP Index in descending order
            buy_signals = buy_signals.sort_values(by=['Bought', 'Buy-Sell Ratio', 'DP Index'], ascending=False).head(50)

            if not buy_signals.empty:
                st.write("### Stocks with Buy Signals")
                st.dataframe(buy_signals[['Symbol', 'Date', 'Closing Price', 'Bought', 'Sold', 'Buy-Sell Ratio','DP Index', 'DP Index 5D', 'DP Index 2W', 'DP Index 1M']], use_container_width=True)
            else:
                st.write("No buy signals detected for the selected period.")
        else:
            st.warning("No data available for the selected range.")

with tabs[4]:
    st.header("Accumulation")

    # Inputs
    end_date = st.date_input("End Date:", value=datetime.today(), key="accumulation_end_date")
    start_date = end_date - timedelta(days=7)
    analysis_start_date = end_date - timedelta(days=2)
    min_volume = st.number_input("Minimum Volume (Bought and Sold):", value=1_000_000, step=100_000, key="min_volume_acc")
    price_threshold = st.number_input("Price Threshold (Default $10):", value=5.0, step=1.0, key="price_threshold_acc")


    if st.button("Find accumulation"):
        # Adjust end_date for market close data availability
        if datetime.now().time() < datetime.strptime("17:00", "%H:%M").time():
            end_date = end_date - timedelta(days=1)

        # Filter out weekends
        dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        dates = [date for date in dates if date.weekday() < 5]  # Exclude weekends

        data_frames = []
        for date in dates:
            daily_data = get_data_for_date(date)
            if daily_data is not None:
                if not daily_data.empty:
                    daily_data['Date'] = date
                    data_frames.append(daily_data)

        if data_frames:
            data = pd.concat(data_frames, ignore_index=True)

            # Process data
            data['Bought'] = data['ShortVolume']  # Assuming ShortVolume as Bought
            data['Sold'] = data['TotalVolume'] - data['ShortVolume']
            data['Total Volume'] = data['Bought'] + data['Sold']
            data['Buy-Sell Ratio'] = data['Bought'] / data['Sold']
            data['% Avg'] = data['Total Volume'] / data['Total Volume'].mean() * 100
            data['DP Index'] = (data['Bought'] / data['Total Volume'] * 100).round(2)

            # Format Date
            data['Date'] = pd.to_datetime(data['Date']).dt.strftime('%Y-%m-%d')

            # Identify accumulation patterns
            #data['Accumulation'] = data['Buy-Sell Ratio'] > 1.25
            data['Accumulation'] = (data['Buy-Sell Ratio'] > 1.25) & (data['DP Index'] > 47)
            data['Rolling Accumulation'] = data['Accumulation'].rolling(window=5, min_periods=5).sum() >= 3

            # accumulation_dates = data.loc[data['Rolling Accumulation'], 'Date'].tolist()
            # accumulation_dates = list(set(accumulation_dates))

            # if accumulation_dates:
            #     st.markdown("### **Accumulation Detected**")
            #     st.markdown(f"The following dates show consistent accumulation over the period:")
            #     for date in accumulation_dates:
            #         st.markdown(f"- **{date}**")
            # else:
            #     st.markdown("### **No Accumulation Detected**")


            # Filter the data to show only accumulation
            data = data[data['Accumulation']]
            data = data[data['Rolling Accumulation']]

            # # Filter to get only Buy-Sell Ratio > 1.25 and DP Index > 50
            # data = data[(data['Buy-Sell Ratio'] > 1.25) & (data['DP Index'] > 50)]

            # Filter where min_volume is greater than the input for both Bought and Sold
            data = data[(data['Bought'] >= min_volume) & (data['Sold'] >= min_volume)]

            # Filter where Date is greater than or equal to the start_date
            data = data[data['Date'] > analysis_start_date.strftime('%Y-%m-%d')]

            unique_symbols = data['Symbol'].unique()
            closing_prices = fetch_closing_prices(unique_symbols)
            data['Closing Price'] = data['Symbol'].map(closing_prices)
            data = data[data['Closing Price'] > price_threshold]

            # Convert the data type of the 'Date' column to Date
            #data['Date'] = pd.to_datetime(data['Date']).dt.strftime('%Y-%m-%d')
        
            # Convert end_date to DateTime
            #end_date = pd.to_datetime(end_date).strftime('%Y-%m-%d')

            # Filter the date to show only the last 5 days
            #data = data[(data['Date'] >= end_date - timedelta(days=5)) & (data['Date'] <= end_date)]

            # Sort the data by Buy-Sell Ratio, DP Index, and Bought Volume in descending order
            data = data.sort_values(by=['Date', 'Buy-Sell Ratio', 'DP Index', 'Bought'], ascending=False).head(50)

            # Create summary table
            table_data = data[['Date', 'Symbol', 'Closing Price', 'Bought', 'Sold', '% Avg', 'Buy-Sell Ratio', 'DP Index', 'Total Volume', 'Accumulation', 'Rolling Accumulation']]
            st.write("### Accumulation Table")
            st.dataframe(table_data, use_container_width=True)

        else:
            st.warning("No data available for the selected range and symbol.")

# Ticker Analysis Tab
with tabs[5]:
    st.header("Filter Analysis")

    # Inputs
    symbol = st.text_input("Enter the symbol (e.g., SPY):", value="").strip().upper()
    end_date = st.date_input("End Date:", value=datetime.today(), key="filter_end_date")
    start_date = end_date - timedelta(days=180)
    min_volume = st.number_input("Minimum Volume (Bought and Sold):", value=1_000_000, step=100_000, key="min_volume_filter")

      # Find out if it's Monday, start date should be last friday, otherwise day before
    if end_date.weekday() == 0:
        analysis_start_date = end_date - timedelta(days=3)
    else:
        analysis_start_date = end_date - timedelta(days=1)

    analysis_start_date = st.date_input("Analysis Start Date:", value=analysis_start_date, key="accumulation_start_date", disabled=True)
  
    price_threshold = st.number_input("Price Threshold (Default $10):", value=5.0, step=1.0, key="price_threshold_filter")
    buy_sell_ratio = st.number_input("Buy-Sell Ratio Threshold (Default 1.25):", value=1.25, step=0.25, key="buy_sell_ratio")
    dp_index = st.number_input("DP Index Threshold (Default 50):", value=50, step=1, key="dp_index")
    buy_or_sell = st.selectbox("Buy or Sell:", ["Buy", "Sell"], index=0)


    if st.button("Filter Analysis"):
        base_url = "https://cdn.finra.org/equity/regsho/daily/"
        filename = f"CNMSshvol{end_date.strftime('%Y%m%d')}.txt"
        file_path = os.path.join(DATA_DIR, filename)
        if os.path.exists(file_path):
        #if datetime.now().time() < datetime.strptime("17:00", "%H:%M").time():
            end_date = end_date
        else:
            end_date = end_date - timedelta(days=1)

        # Filter out weekends
        dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        dates = [date for date in dates if date.weekday() < 5]  # Exclude weekends

        data_frames = []
        for date in dates:
            daily_data = get_data_for_date(date)
            if daily_data is not None:
                if symbol:
                    daily_data = daily_data[daily_data['Symbol'] == symbol]
                if not daily_data.empty:
                    daily_data['Date'] = date
                    data_frames.append(daily_data)

        if data_frames:
            data = pd.concat(data_frames, ignore_index=True)

            # Process data
            data['Bought'] = data['ShortVolume']  # Assuming ShortVolume as Bought
            data['Sold'] = data['TotalVolume'] - data['ShortVolume']
            data['Total Volume'] = data['Bought'] + data['Sold']
            data['Buy-Sell Ratio'] = data['Bought'] / data['Sold']
            data['% Avg'] = data['Total Volume'] / data['Total Volume'].mean() * 100
            data['DP Index'] = (data['Bought'] / data['Total Volume'] * 100).round(2)

            # Format Date
            data['Date'] = pd.to_datetime(data['Date']).dt.strftime('%Y-%m-%d')

            data['Cumulative Buying'] = data['Bought'].rolling(window=2, min_periods=1).sum()
            data['Cumulative Selling'] = data['Sold'].rolling(window=2, min_periods=1).sum()

            # Fiter volume
            data = data[(data['Bought'] >= min_volume) & (data['Sold'] >= min_volume)]

            # Filter Buy-Sell Ratio
            if (buy_or_sell == "Buy"):
                data = data[data['Buy-Sell Ratio'] >= buy_sell_ratio]
            else:
                data = data[data['Buy-Sell Ratio'] <= buy_sell_ratio]

            # Filter by DP Index
            if (buy_or_sell == "Buy"):
                data = data[data['DP Index'] >= dp_index]
            else:
                data = data[data['DP Index'] <= dp_index]

            data = data[data['Date'] >= analysis_start_date.strftime('%Y-%m-%d')]

            unique_symbols = data['Symbol'].unique()
            closing_prices = fetch_closing_prices(unique_symbols)
            data['Closing Price'] = data['Symbol'].map(closing_prices)
            data = data[data['Closing Price'] > price_threshold]

            # Color coding
            def highlight_row(row):
                if row['Bought'] > row['Sold']:
                    return ["background-color: yellow"] + ["background-color: lightgreen"] * 8 + ["background-color: lightgreen"]
                else:
                    return ["background-color: yellow"] + ["background-color: lightcoral"] * 8 + ["background-color: lightcoral"]

            # Filter the data to show last 30 days in descending order
            if buy_or_sell == "Buy":
                # sort data by Buy-Sell Ratio, DP Index, and Bought Volume in descending order
                data = data.sort_values(by=['Date', 'Buy-Sell Ratio', 'DP Index', 'Bought'], ascending=False)
            else:
                # sort data by Buy-Sell Ratio, DP Index, and Sold Volume in descending order
                data = data.sort_values(by=['Date', 'Buy-Sell Ratio', 'DP Index', 'Sold'], ascending=False)

            # Create summary table
            table_data = data[['Date', 'Symbol', 'Closing Price', 'Bought', 'Sold', '% Avg', 'Buy-Sell Ratio', 'DP Index', 'Total Volume', 'Cumulative Buying', 'Cumulative Selling']]
            styled_table = table_data.style.apply(highlight_row, axis=1)
            st.write("### Dark Volume Table")
            #st.dataframe(styled_table.format(precision=2), use_container_width=True)
            st.dataframe(table_data, use_container_width=True)
        else:
            st.warning("No data available for the selected range and symbol.")
            
with tabs[6]:
    st.header("Accumulation Analysis")

    # Inputs
    end_date = st.date_input("End Date:", value=datetime.today(), key="accumulation_analysis_end_date")
    start_date = end_date - timedelta(days=180)
    min_volume = st.number_input("Minimum Volume (Bought and Sold):", value=1000000, step=100000, key="min_volume_filter_accumulation_analysis")

    if st.button("Run Accumulation Analysis"):
        # Adjust end_date for market close data availability
        if datetime.now().time() < datetime.strptime("17:00", "%H:%M").time():
            end_date = end_date - timedelta(days=1)

        base_url = "https://cdn.finra.org/equity/regsho/daily/"
        filename = f"CNMSshvol{analysis_end_date.strftime('%Y%m%d')}.txt"
        file_path = os.path.join(DATA_DIR, filename)
        if os.path.exists(file_path):
            analysis_end_date = analysis_end_date
        else:
            analysis_end_date = analysis_end_date - timedelta(days=1)

        # Filter out weekends
        dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
        dates = [date for date in dates if date.weekday() < 5]  # Exclude weekends

        data_frames = []
        for date in dates:
            daily_data = get_data_for_date(date)
            if daily_data is not None:
                if not daily_data.empty:
                    daily_data['Date'] = date
                    data_frames.append(daily_data)

        if data_frames:
            data = pd.concat(data_frames, ignore_index=True)

            # Process data
            data['Bought'] = data['ShortVolume']  # Assuming ShortVolume as Bought
            data['Sold'] = data['TotalVolume'] - data['ShortVolume']
            data['Total Volume'] = data['Bought'] + data['Sold']
            data['Buy-Sell Ratio'] = data['Bought'] / data['Sold']
            data['% Avg'] = data['Total Volume'] / data['Total Volume'].mean() * 100
            data['DP Index'] = (data['Bought'] / data['Total Volume'] * 100).round(2)

            # Format Date
            data['Date'] = pd.to_datetime(data['Date']).dt.strftime('%Y-%m-%d')

            # # Identify accumulation patterns based on the symbol (groupby)
            # combined_data = data.groupby('Symbol').apply(lambda x: x['Buy-Sell Ratio'] > 1.25).rolling(window=5, min_periods=5).sum() >= 5

            # # Get accumulation symbols and dates
            # accumulation_symbols = combined_data[combined_data].index.get_level_values(0).tolist()
            # accumulation_dates = combined_data[combined_data].index.get_level_values(1).tolist()

            # # Create summary table that shows the accumulation symbols and dates. Ensure  that the data is grouped such that multiple dates are shown for each symbol
            # table_data = pd.DataFrame({
            #     'Symbol': accumulation_symbols,
            #     'Date': accumulation_dates
            # })

             # Identify accumulation patterns
            data['Accumulation'] = (data['Buy-Sell Ratio'] > 1.25)
            #data['Rolling Accumulation'] = data['Accumulation'].rolling(window=5, min_periods=5).sum() >= 5
            data['Rolling Accumulation'] = data.groupby('Symbol')['Accumulation'].transform(lambda x: x.rolling(window=5, min_periods=5).sum() >= 5)
            data['Rolling Accumulation'] = data['Rolling Accumulation'].fillna(False)
            data['Five_Accumulation'] = data.groupby('Symbol')['Rolling Accumulation'].transform(lambda x: x.tail(5).any())

            #combined_data = data.groupby('Symbol').apply(lambda x: x['Buy-Sell Ratio'] > 1.25).rolling(window=5, min_periods=5).sum() >= 5
            #combined_data = combined_data[combined_data['Buy-Sell Ratio']]

            # Filter the data to show only accumulation
            data = data[data['Accumulation']]
            data = data[data['Rolling Accumulation']]

            data = data[data['Date'] >= analysis_end_date.strftime('%Y-%m-%d')]

            # Fiter volume
            data = data[(data['Bought'] >= min_volume) & (data['Sold'] >= min_volume)]
            data.reset_index(drop=True, inplace=True)

            # sort the data by Date
            table_data = data[['Date', 'Symbol', 'Bought', 'Sold', '% Avg', 'Buy-Sell Ratio', 'DP Index', 'Total Volume']]
            st.write("### Accumulation Table")
            st.dataframe(table_data, use_container_width=True)
        else:
            st.warning("No data available for the selected range and symbol.")