import json
import os
import time
from groq import Groq

# ==========================================
# 1. 設定 API Key 與路徑
# ==========================================
client = Groq(api_key=os.environ.get("GROQ_API_KEY", "YOUR_API_KEY_HERE")) # <--- 請替換成你的 Groq API Key
WIKI_DIR = "wiki"
OUTPUT_HTML = "index.html"

# 優先選擇高速且穩定的純文字模型，避開語音與易截斷模型
all_models = [m.id for m in client.models.list().data]
fast_models = [
    m
    for m in all_models
    if "llama-3.1-8b" in m.lower() or "llama-3.3-70b" in m.lower()
]
fallback_models = [
    m
    for m in all_models
    if any(k in m.lower() for k in ["llama", "qwen", "gemma"])
    and not any(
        bad in m.lower() for bad in ["whisper", "guard", "orpheus", "tts"]
    )
]
MODEL_NAME = fast_models[0] if fast_models else fallback_models[0]
print(f"🤖 簡報生成系統啟動，使用模型：{MODEL_NAME}\n")

# 定義 7 頁投影片與對應的 Wiki 檔案
SLIDE_PLAN = [
    {
        "page": 1,
        "topic": "課程總覽：計算機概論—數位邏輯與資料表示法入門",
        "wiki": "index.md",
    },
    {
        "page": 2,
        "topic": "進位制與補數系統（1's 與 2's 補數）",
        "wiki": "01_補數.md",
    },
    {
        "page": 3,
        "topic": "資料傳輸守護者：奇偶校驗與漢明碼 (Hamming Code)",
        "wiki": "02_漢明碼.md",
    },
    {
        "page": 4,
        "topic": "數位電路積木：基本邏輯閘與萬用閘",
        "wiki": "03_邏輯閘.md",
    },
    {
        "page": 5,
        "topic": "布林代數標準式：積之和 (SOP) 與和之積 (POS)",
        "wiki": "04_SOP_POS.md",
    },
    {
        "page": 6,
        "topic": "化繁為簡的利器：卡諾圖 (K-Map) 化簡",
        "wiki": "05_卡諾圖.md",
    },
    {"page": 7, "topic": "全章重點總結與初學者複習路徑", "wiki": "index.md"},
]


def read_single_wiki(filename):
  path = os.path.join(WIKI_DIR, filename)
  if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
      return f.read()[:1500]
  return ""


def generate_one_slide(plan_item, wiki_text, feedback=""):
  revision = (
      f"\n【⚠️ 上一版被檢查節點退回，請修正以下錯誤】：\n{feedback}\n"
      if feedback
      else ""
  )
  prompt = f"""
你是擅長把計算機概論講給完全沒基礎的人聽的講師。請根據【Wiki 知識庫內容】，為「{plan_item['topic']}」撰寫第 {plan_item['page']} 頁教學投影片。
{revision}
【編寫規範】
1. 用生活比喻解釋概念，並附一個簡單數字手算範例。
2. 新增 `must_remember` 欄位：寫 1 到 3 句「其他全忘了沒關係，但這一頁一定要帶走的核心觀念」（就像出去玩必吃的名產一樣好記）。
3. 必須輸出合法的 JSON 物件，格式如下：
{{
  "page": {plan_item['page']},
  "title": "投影片標題",
  "subtitle": "生活比喻 + 一句話白話概念",
  "source_wiki": "{plan_item['wiki']}",
  "points": [
    "【為什麼需要它】白話說明",
    "【怎麼運作】簡單步驟或口訣",
    "【實際算算看】一個具體小例子"
  ],
  "tip": "初學者最容易搞混的小提醒",
  "must_remember": [
    "必記重點 1（一句話）",
    "必記重點 2（一句話）"
  ]
}}

【Wiki 知識庫內容】
{wiki_text}
"""
  res = client.chat.completions.create(
      model=MODEL_NAME,
      messages=[{"role": "user", "content": prompt}],
      temperature=0.2,
      max_tokens=1500,
      response_format={"type": "json_object"},
      reasoning_effort="none",
  )
  return res.choices[0].message.content


def verify_one_slide(wiki_text, slide_json_str):
  prompt = f"""
你是計概教材品管員。請核對【單頁投影片 JSON】：
1. 是否包含 title, subtitle, points, tip, speaker_note 等完整欄位？
2. 裡面的二進位補數、漢明碼、邏輯閘或 SOP/POS 基本規則是否合理？（只要大方向正確且欄位完整即可回答 `PASS: YES`，無須吹毛求疵退回）。

第一行請只回答 `PASS: YES` 或 `PASS: NO`。若為 NO，第二行起列出具體錯誤。

【單頁投影片 JSON】
{slide_json_str}
"""
  
  res = client.chat.completions.create(
      model=MODEL_NAME,
      messages=[{"role": "user", "content": prompt}],
      temperature=0.1,
      max_tokens=800,
      reasoning_effort="none",
  )
  return res.choices[0].message.content


def render_html_slides(slides_data):
  slides_json = json.dumps(slides_data, ensure_ascii=False)
  html_template = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>計算機概論：數位邏輯入門教學簡報</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif; }}
        body {{ background: #0f172a; color: #f8fafc; min-height: 100vh; display: flex; flex-direction: column; }}
        .progress-bar {{ height: 6px; background: #1e293b; width: 100%; }}
        .progress-fill {{ height: 100%; background: #38bdf8; width: 0%; transition: width 0.3s ease; }}
        .slide-container {{ flex: 1; display: flex; justify-content: center; align-items: center; padding: 1.5rem; }}
        .slide-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 16px; max-width: 920px; width: 100%; padding: 2.2rem 2.8rem; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }}
        .badge {{ display: inline-block; background: #0284c7; color: #e0f2fe; padding: 0.3rem 0.8rem; border-radius: 999px; font-size: 0.85rem; margin-bottom: 0.8rem; }}
        h1 {{ font-size: 2rem; color: #38bdf8; margin-bottom: 0.5rem; }}
        .subtitle {{ font-size: 1.15rem; color: #94a3b8; margin-bottom: 1.5rem; border-left: 4px solid #38bdf8; padding-left: 1rem; }}
        ul {{ list-style: none; margin-bottom: 1.5rem; }}
        li {{ font-size: 1.08rem; line-height: 1.65; margin-bottom: 0.8rem; padding-left: 1.5rem; position: relative; }}
        li::before {{ content: "▸"; color: #38bdf8; position: absolute; left: 0; font-weight: bold; }}
        .tip-box {{ background: #0f172a; border-left: 4px solid #f59e0b; padding: 0.9rem 1.2rem; border-radius: 8px; color: #fde68a; font-size: 0.98rem; }}
        .note-box {{ margin-top: 0.9rem; background: #020617; border: 1px solid #334155; padding: 0.9rem 1.2rem; border-radius: 8px; color: #cbd5e1; font-size: 0.95rem; line-height: 1.6; }}
        .controls {{ display: flex; justify-content: space-between; align-items: center; padding: 1rem 3rem; background: #020617; border-top: 1px solid #1e293b; }}
        button {{ background: #38bdf8; color: #0f172a; border: none; padding: 0.6rem 1.4rem; border-radius: 8px; font-size: 1rem; font-weight: bold; cursor: pointer; }}
        button:disabled {{ background: #334155; color: #64748b; cursor: not-allowed; }}
        .page-info {{ color: #94a3b8; font-size: 0.95rem; }}
    </style>
</head>
<body>
    <div class="progress-bar"><div class="progress-fill" id="progress"></div></div>
    <div class="slide-container">
        <div class="slide-card" id="slide-content"></div>
    </div>
    <div class="controls">
        <button id="prev-btn" onclick="changeSlide(-1)">← 上一頁</button>
        <span class="page-info" id="page-info"></span>
        <button id="next-btn" onclick="changeSlide(1)">下一頁 →</button>
    </div>
    <script>
        const slides = {slides_json};
        let current = 0;
        function render() {{
            const s = slides[current];
            document.getElementById('slide-content').innerHTML = `
                <span class="badge">📚 知識來源：${{s.source_wiki}}</span>
                <h1>${{s.title}}</h1>
                <div class="subtitle">${{s.subtitle}}</div>
                <ul>${{(s.points || []).map(p => `<li>${{p}}</li>`).join('')}}</ul>
                <div class="tip-box">💡 <strong>初學者防呆提醒：</strong>${{s.tip}}</div>
                <div class="note-box">
                    🎒 <strong>其他忘了沒關係，這幾句一定要帶走：</strong>
                    <ul style="margin-top: 0.5rem; margin-bottom: 0;">
                        ${{(s.must_remember || []).map(m => `<li style="font-size: 0.98rem; margin-bottom: 0.3rem;">${{m}}</li>`).join('')}}
                    </ul>
                </div>
            `;
            document.getElementById('page-info').innerText = `第 ${{current + 1}} 頁 / 共 ${{slides.length}} 頁（支援鍵盤 ← → 切換）`;
            document.getElementById('progress').style.width = `${{((current + 1) / slides.length) * 100}}%`;
            document.getElementById('prev-btn').disabled = current === 0;
            document.getElementById('next-btn').disabled = current === slides.length - 1;
        }}
        function changeSlide(dir) {{
            current = Math.max(0, Math.min(slides.length - 1, current + dir));
            render();
        }}
        document.addEventListener('keydown', e => {{
            if (e.key === 'ArrowRight') changeSlide(1);
            if (e.key === 'ArrowLeft') changeSlide(-1);
        }});
        render();
    </script>
</body>
</html>"""
  with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html_template)


def main():
  final_slides = []
  for item in SLIDE_PLAN:
    wiki_text = read_single_wiki(item["wiki"])
    feedback = ""
    slide_obj = None

    for attempt in range(1, 3):
      print(
          f"📄 [第 {item['page']} 頁] 第 {attempt} 次生成（來源：{item['wiki']}）..."
      )
      raw = generate_one_slide(item, wiki_text, feedback).strip()
      time.sleep(2)

      check = verify_one_slide(wiki_text, raw)
      print(f"🔍 [檢查結果] {check.splitlines()[0]}")
      time.sleep(2)

      try:
        slide_obj = json.loads(raw)
        if "PASS: YES" in check.upper():
          break
        else:
          print(f"⚠️ 退回重寫原因：\n{check}")
          feedback = check
      except Exception as e:
        print(f"⚠️ JSON 格式修正中：{e}")
        feedback = f"JSON 格式錯誤：{e}"

    if slide_obj:
      final_slides.append(slide_obj)

  render_html_slides(final_slides)
  print(f"\n🎉 成功生成完整 {len(final_slides)} 頁簡報：`{OUTPUT_HTML}`！")


if __name__ == "__main__":
  main()