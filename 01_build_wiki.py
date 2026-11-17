import os
import time
from groq import Groq
from pypdf import PdfReader

# ==========================================
# 1. 設定 API Key 與資料夾路徑
# ==========================================
client = Groq(api_key=os.environ.get("GROQ_API_KEY", "YOUR_API_KEY_HERE"))  # <--- 請替換成你的 Groq API Key

RAW_DIR = "raw_sources"
WIKI_DIR = "wiki"
os.makedirs(WIKI_DIR, exist_ok=True)

# 只篩選純文字生成模型
all_models = [m.id for m in client.models.list().data]
print("📋 你的帳號可用模型：", all_models)

text_models = [
    m
    for m in all_models
    if any(k in m.lower() for k in ["llama", "qwen", "gemma", "gpt"])
    and not any(bad in m.lower() for bad in ["whisper", "guard", "orpheus", "tts"])
]
MODEL_NAME = text_models[0]
print(f"🤖 自動選用文字模型：{MODEL_NAME}")


def extract_text_from_pdf(pdf_path):
  """從 PDF 抽取純文字，只取前 6,000 字元以節省免費 API 額度"""
  reader = PdfReader(pdf_path)
  full_text = []
  for page in reader.pages:
    text = page.extract_text()
    if text:
      full_text.append(text)
  combined = "\n".join(full_text)
  return combined[:6000]


def ingest_to_wiki(filename, raw_text, all_topics):
  """呼叫 Groq API 將原始文獻轉化為結構化的 Wiki 詞條"""
  prompt = f"""
你是一位計算機概論助教，正在建立「數位邏輯與資料表示法」的 LLM Wiki 知識庫。
請根據以下原始資料（檔名：{filename}），整理成一篇結構清晰、適合初學者的繁體中文 Markdown Wiki 頁面。

【Wiki 規範】
1. 包含區塊：`# 標題`、`## 核心概念一句話`、`## 詳細原理與規則`、`## 具體計算範例`、`## 常見誤區`、`## 相關連結`（從 {all_topics} 挑選有關聯的加上 `[[檔名]]`）。
2. 嚴格忠於原始資料，不可編造未提及的規則。

【原始資料】
{raw_text}
"""
  response = client.chat.completions.create(
      model=MODEL_NAME,
      messages=[{"role": "user", "content": prompt}],
      temperature=0.2,
  )
  return response.choices[0].message.content


def generate_wiki_index(wiki_summaries):
  """建立 Wiki 總目錄 index.md"""
  prompt = f"""
我們已建立以下幾篇「計算機概論：數位邏輯」Wiki 詞條：
{wiki_summaries}

請撰寫總首頁 `index.md`（繁體中文），包含：1. 知識庫簡介 2. 初學者學習順序建議 3. 詞條總覽表。
"""
  response = client.chat.completions.create(
      model=MODEL_NAME,
      messages=[{"role": "user", "content": prompt}],
      temperature=0.3,
  )
  return response.choices[0].message.content


def main():
  pdf_files = sorted([f for f in os.listdir(RAW_DIR) if f.endswith(".pdf")])
  if not pdf_files:
    print(f"❌ 在 {RAW_DIR}/ 找不到 PDF 檔案！")
    return

  print(f"📂 找到 {len(pdf_files)} 份 PDF，開始省額度模式 Ingest...\n")
  all_topics = [os.path.splitext(f)[0] + ".md" for f in pdf_files]
  wiki_summaries = []

  for pdf_file in pdf_files:
    pdf_path = os.path.join(RAW_DIR, pdf_file)
    md_filename = os.path.splitext(pdf_file)[0] + ".md"
    md_path = os.path.join(WIKI_DIR, md_filename)

    print(f"⏳ 解析：{pdf_file} ...")
    raw_text = extract_text_from_pdf(pdf_path)

    print(f"🤖 生成 Wiki：{md_filename} ...")
    wiki_content = ingest_to_wiki(pdf_file, raw_text, all_topics)

    with open(md_path, "w", encoding="utf-8") as f:
      f.write(wiki_content)

    wiki_summaries.append(f"### {md_filename}\n{wiki_content[:200]}...\n")
    print(f"✅ 完成：{md_path}（冷卻 3 秒保護額度）\n")
    time.sleep(3)

  print("📑 生成總目錄 index.md ...")
  index_content = generate_wiki_index("\n".join(wiki_summaries))
  with open(os.path.join(WIKI_DIR, "index.md"), "w", encoding="utf-8") as f:
    f.write(index_content)

  print(f"🎉 Wiki 建立完成！請查看 `{WIKI_DIR}/` 資料夾。")


if __name__ == "__main__":
  main()