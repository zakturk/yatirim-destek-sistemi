
import streamlit as st
import pandas as pd
import os
import base64

st.set_page_config(page_title="BIST100 Drawdown Dashboard", layout="wide")

st.markdown("<div id='top'></div>", unsafe_allow_html=True)

st.title("📉 BIST100 En Büyük Drawdown Görsel Paneli")
st.write("Bu panel, en fazla düşüş yaşayan hisseleri ve özet bilgilerini sunar.")

summary_path = os.path.join("stock_data", "top10_summary.csv")

def image_to_html_base64(path):
    with open(path, "rb") as f:
        data = f.read()
    encoded = base64.b64encode(data).decode()
    html = f'<img src="data:image/png;base64,{encoded}" style="width:100%;border:1px solid #ccc;border-radius:10px;" />'
    return html

if not os.path.exists(summary_path):
    st.warning("⚠️ Top10 özet dosyası bulunamadı. Lütfen veri çekim sürecini çalıştırın.")
else:
    df = pd.read_csv(summary_path)

    def render_row(row):
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(image_to_html_base64(row["Grafik"]), unsafe_allow_html=True)
        with col2:
            st.markdown(f"**Max Drawdown:** {row['Max Drawdown']}")
            st.markdown(f"**Son Güncelleme:** {row['Son Tarih']}")
            st.markdown(f"**Veri Satırı:** {row['Satır Sayısı']}")
            st.markdown(f"[📄 CSV'yi Görüntüle]({row['CSV Dosyası']})")

            signal = row.get("Sinyal", "BEKLE")
            if signal == "AL":
                st.markdown("📈 **Sinyal: AL**", unsafe_allow_html=True)
            elif signal == "SAT":
                st.markdown("📉 **Sinyal: SAT**", unsafe_allow_html=True)
            else:
                st.markdown("⏸️ **Sinyal: BEKLE**", unsafe_allow_html=True)

    for i in range(len(df)):
        render_row(df.iloc[i])
        st.markdown("""
        <a href="#top" style="text-decoration:none;font-size:16px;">Yukarı çık 🔝</a>
        <script>
            const anchor = document.getElementById("top");
            if (!anchor) {
                const div = document.createElement("div");
                div.id = "top";
                document.body.prepend(div);
            }
        </script>
        """, unsafe_allow_html=True)
        st.markdown("---")
