
import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import requests
import bs4 as bs
from datetime import datetime
from tqdm import tqdm
from isyatirimhisse import StockData
import ta

plt.style.use("fivethirtyeight")

def log_message(message, base_folder="stock_data"):
    log_path = os.path.join(base_folder, "log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def read_metadata(symbol, folder_path):
    meta_path = os.path.join(folder_path, f"{symbol}_metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_metadata(symbol, df, csv_path, graph_path, folder_path, signal=None):
    metadata = {
        "symbol": symbol,
        "last_update": df["DATE"].max().strftime("%Y-%m-%d"),
        "rows": len(df),
        "max_drawdown": float(df["Drawdown"].min()),
        "csv_path": csv_path,
        "graph_path": graph_path,
        "signal": signal
    }
    meta_path = os.path.join(folder_path, f"{symbol}_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    return metadata

def calculate_technical_indicators(df):
    df = df.copy()
    df["RSI"] = ta.momentum.RSIIndicator(close=df["CLOSING_TL"], window=14).rsi()
    macd = ta.trend.MACD(close=df["CLOSING_TL"])
    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()
    df["EMA20"] = ta.trend.EMAIndicator(close=df["CLOSING_TL"], window=20).ema_indicator()
    df["EMA50"] = ta.trend.EMAIndicator(close=df["CLOSING_TL"], window=50).ema_indicator()
    return df

def generate_signal(row):
    rsi_signal = macd_signal = ema_signal = ""
    if row["RSI"] < 30: rsi_signal = "AL"
    elif row["RSI"] > 70: rsi_signal = "SAT"
    if row["MACD"] > row["MACD_SIGNAL"]: macd_signal = "AL"
    elif row["MACD"] < row["MACD_SIGNAL"]: macd_signal = "SAT"
    if row["EMA20"] > row["EMA50"]: ema_signal = "AL"
    elif row["EMA20"] < row["EMA50"]: ema_signal = "SAT"
    signals = [rsi_signal, macd_signal, ema_signal]
    if signals.count("AL") >= 2: return "AL"
    elif signals.count("SAT") >= 2: return "SAT"
    else: return "BEKLE"

def setup_environment():
    while True:
        start_date = input("Veri çekimine başlamak istediğiniz tarihi girin (GG-AA-YYYY): ")
        try:
            datetime.strptime(start_date, "%d-%m-%Y")
            break
        except ValueError:
            print("Hatalı format. Lütfen GG-AA-YYYY şeklinde girin.")
    base_folder = 'stock_data'
    os.makedirs(base_folder, exist_ok=True)
    return start_date, base_folder

def get_xu100_list():
    url = "https://tr.wikipedia.org/wiki/Borsa_%C4%B0stanbul"
    resp = requests.get(url)
    soup = bs.BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"class": "wikitable"})
    tickers = []
    for row in table.findAll("tr")[1:]:
        try:
            ticker = row.findAll("td")[0].text.strip().replace("İ", "I")
            tickers.append(ticker)
        except:
            continue
    return tickers

def update_or_create_stock_data(symbol, start_date, base_folder):
    stock_data = StockData()
    symbol_folder = os.path.join(base_folder, symbol)
    os.makedirs(symbol_folder, exist_ok=True)
    csv_path = os.path.join(symbol_folder, f"{symbol}_drawdown_data.csv")
    graph_path = os.path.join(symbol_folder, f"{symbol}_drawdown_graph.png")
    log_message(f"{symbol}: işlem başlatıldı.", base_folder)

    if os.path.exists(csv_path):
        existing_df = pd.read_csv(csv_path, parse_dates=["DATE"])
        last_date = existing_df["DATE"].max().strftime("%d-%m-%Y")
        start_date_to_fetch = last_date
    else:
        existing_df = pd.DataFrame()
        start_date_to_fetch = start_date

    try:
        df_new = stock_data.get_data(symbols=symbol, start_date=start_date_to_fetch)[["DATE", "CLOSING_TL"]]
        df_new = df_new.dropna()
        df_new["DATE"] = pd.to_datetime(df_new["DATE"])
        df_new = df_new.sort_values("DATE")
        df_new["RETURN"] = df_new["CLOSING_TL"].pct_change()
        df_new = df_new.dropna()

        if not existing_df.empty:
            combined = pd.concat([existing_df, df_new]).drop_duplicates(subset=["DATE"]).sort_values("DATE")
        else:
            combined = df_new

        combined = calculate_technical_indicators(combined)
        latest_row = combined.iloc[-1]
        signal = generate_signal(latest_row)
        log_message(f"{symbol}: Sinyal üretildi → {signal}", base_folder)

        combined.to_csv(csv_path, index=False)
        combined['Cumulative Returns'] = (1 + combined['RETURN']).cumprod()
        combined['Maximum Peak'] = combined['Cumulative Returns'].cummax()
        combined['Drawdown'] = combined['Cumulative Returns'] / combined['Maximum Peak'] - 1
        drawdown_min = combined["Drawdown"].min()

        plt.figure(figsize=(10, 6))
        plt.plot(combined["DATE"], combined["Drawdown"], color='red', label='Drawdown')
        plt.fill_between(combined["DATE"], combined["Drawdown"], where=combined["Drawdown"] < 0, color='red', alpha=0.3)
        plt.axhline(y=drawdown_min, color='black', linestyle='--', label=f'Max Drawdown: {abs(drawdown_min):.2%}')
        plt.title(f"{symbol} Drawdown Chart")
        plt.xlabel("Tarih")
        plt.ylabel("Drawdown")
        plt.legend()
        plt.tight_layout()
        plt.savefig(graph_path)
        plt.close()

        previous_meta = read_metadata(symbol, symbol_folder)
        if previous_meta:
            old = previous_meta.get("max_drawdown", 0)
            fark = drawdown_min - old
            if fark < 0:
                log_message(f"{symbol}: Drawdown kötüleşti. Önceki: {old:.2%}, Yeni: {drawdown_min:.2%}", base_folder)
            elif fark > 0:
                log_message(f"{symbol}: Drawdown iyileşti. Önceki: {old:.2%}, Yeni: {drawdown_min:.2%}", base_folder)
            else:
                log_message(f"{symbol}: Drawdown değişmedi: {drawdown_min:.2%}", base_folder)
        else:
            log_message(f"{symbol}: İlk çalıştırma, kıyas yok.", base_folder)

        save_metadata(symbol, combined, csv_path, graph_path, symbol_folder, signal=signal)
        log_message(f"{symbol}: metadata dosyası kaydedildi.", base_folder)
        return combined

    except Exception as e:
        log_message(f"{symbol}: HATA - {e}", base_folder)
        print(f"HATA ({symbol}): {e}")
        return None

def run_all():
    start_date, base_folder = setup_environment()
    xu100_list = get_xu100_list()
    print(f"\n🧾 Toplam {len(xu100_list)} hisse bulundu. İşleme başlanıyor...\n")

    results = {}

    for symbol in tqdm(xu100_list, desc="📊 Hisse İşleniyor"):
        df = update_or_create_stock_data(symbol, start_date, base_folder)
        if df is not None and 'Drawdown' in df:
            results[symbol] = df['Drawdown'].min()

    drawdown_series = pd.Series(results)
    top10_symbols = drawdown_series.nsmallest(10).index

    summary_data = []
    for symbol in top10_symbols:
        meta_path = os.path.join(base_folder, symbol, f"{symbol}_metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                summary_data.append({
                    "Hisse": symbol,
                    "Max Drawdown": f"{meta['max_drawdown']:.2%}",
                    "Son Tarih": meta['last_update'],
                    "Satır Sayısı": meta['rows'],
                    "CSV Dosyası": meta['csv_path'],
                    "Grafik": meta['graph_path'],
                    "Sinyal": meta.get('signal', "BEKLE")
                })

    summary_df = pd.DataFrame(summary_data)
    summary_df.index += 1

    print("\n📉 En yüksek max drawdown'a sahip ilk 10 hisse:")
    print(summary_df)

    summary_csv_path = os.path.join(base_folder, "top10_summary.csv")
    summary_df.to_csv(summary_csv_path, index=False, encoding="utf-8-sig")

    log_message("Top 10 tablo dosyası oluşturuldu: top10_summary.csv", base_folder)
    return summary_df

if __name__ == "__main__":
    run_all()
