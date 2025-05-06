import requests, pandas as pd
import matplotlib.pyplot as plt
from config import INDICATOR_WINDOWS

def fetch_historical(coin_id, vs_currency, days):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    res = requests.get(url, params={"vs_currency": vs_currency, "days": days})
    data = res.json()["prices"]
    df = pd.DataFrame(data, columns=["ts","price"])
    df["date"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("date")[["price"]]

def sma(prices, window):    return prices.rolling(window).mean()
def ema(prices, window):    return prices.ewm(span=window, adjust=False).mean()
def rsi(prices, window):
    delta = prices.diff()
    up, down = delta.clip(lower=0), -delta.clip(upper=0)
    ma_up = up.rolling(window).mean()
    ma_down = down.rolling(window).mean()
    rs = ma_up/ma_down
    return 100 - (100/(1+rs))

def macd(df, fast, slow, signal):
    e1 = df.ewm(span=fast, adjust=False).mean()
    e2 = df.ewm(span=slow, adjust=False).mean()
    m_line = e1-e2
    s_line = m_line.ewm(span=signal, adjust=False).mean()
    return m_line, s_line

def bollinger(df, window):
    m = df.rolling(window).mean()
    std = df.rolling(window).std()
    return m + 2*std, m - 2*std

def choose_indicators():
    opts = ["SMA","EMA","RSI","MACD","BB"]
    for i,o in enumerate(opts,1): print(f"{i}. {o}")
    picks = input("Choose (e.g. 1,3): ")
    return [opts[int(i)-1] for i in picks.split(",")]

def generate_signals(df, chosen, params):
    sig = pd.DataFrame(index=df.index)
    price = df["price"]
    votes = pd.DataFrame(index=df.index)

    if "SMA" in chosen:
        sig["sma"] = price > sma(price, params["sma"])
    if "EMA" in chosen:
        sig["ema"] = price > ema(price, params["ema"])
    if "RSI" in chosen:
        r = rsi(price, params["rsi"])
        sig["rsi"] = r < 30
    if "MACD" in chosen:
        m, s = macd(price, params["macd_fast"], params["macd_slow"], params["macd_signal"])
        sig["macd"] = m > s
    if "BB" in chosen:
        up, dn = bollinger(price, params["bb_window"])
        sig["bb"] = price < dn

    sig["buy_votes"] = sig.sum(axis=1)
    sig["sell_votes"] = len(chosen) - sig["buy_votes"]
    sig["signal"] = sig["buy_votes"] > sig["sell_votes"]
    return sig

def plot(df, sig, chosen, params):
    plt.figure(figsize=(12,6))
    plt.plot(df.index, df["price"], label="Price")
    if "SMA" in chosen:
        plt.plot(df.index, sma(df["price"],params["sma"]), label=f"SMA{params['sma']}")
    if "EMA" in chosen:
        plt.plot(df.index, ema(df["price"],params["ema"]), label=f"EMA{params['ema']}")
    buys = sig[sig["signal"] & ~sig["signal"].shift(1)]
    sells = sig[~sig["signal"] & sig["signal"].shift(1)]
    plt.scatter(buys.index, df.loc[buys.index,"price"], marker="^", label="Buy")
    plt.scatter(sells.index, df.loc[sells.index,"price"], marker="v", label="Sell")
    plt.legend(); plt.title("Backtest Signals")
    plt.show()

def main():
    coin = input(f"Coin ({', '.join(COIN_LIST)}): ")
    days = int(input("Days history: "))
    horizon = input("Horizon (short/long): ")
    df = fetch_historical(coin, VS_CURRENCY, days)
    chosen = choose_indicators()
    params = INDICATOR_WINDOWS[horizon]
    sig = generate_signals(df, chosen, params)
    plot(df, sig, chosen, params)
    print(f"Generated {sig['signal'].sum()} buy signals over {days} days.")

if __name__=="__main__":
    main()