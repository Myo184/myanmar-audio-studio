import gradio as gr
import asyncio
import edge_tts
import re
import os
import datetime
import json
from huggingface_hub import HfApi

try:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
except ImportError:
    raise ImportError("ကျေးဇူးပြု၍ requirements.txt တွင် pydub ထည့်ပေးပါ။")

DATASET_REPO = "Paing1213/vip-database-storage" # မိမိ Dataset Repo အမည်သို့ ပြောင်းနိုင်သည်
DB_FILE = "vip_database.json"

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin1234") # Hugging Face Env တွင် ထည့်ရမည်
HF_TOKEN = os.environ.get("HF_TOKEN")
api = HfApi(token=HF_TOKEN)

def load_vip_database():
    if not HF_TOKEN or not os.path.exists(DB_FILE):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: return {}
        return {}
    try:
        from huggingface_hub import hf_hub_download
        filepath = hf_hub_download(repo_id=DATASET_REPO, filename=DB_FILE, repo_type="dataset", token=HF_TOKEN)
        with open(filepath, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_vip_database(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    if HF_TOKEN:
        try:
            try: api.create_repo(repo_id=DATASET_REPO, repo_type="dataset", private=True, exist_ok=True)
            except: pass
            api.upload_file(path_or_fileobj=DB_FILE, path_in_repo=DB_FILE, repo_id=DATASET_REPO, repo_type="dataset")
        except: pass

VIP_PASSWORDS = load_vip_database()

# လစဉ်/နှစ်စဉ် Plan အလိုက် ရက်ပေါင်း သတ်မှတ်ခြင်း
def register_or_renew_vip(admin_pass, user_password, plan_type):
    global VIP_PASSWORDS
    if admin_pass.strip() != ADMIN_PASSWORD: return "❌ Admin Password မမှန်ကန်ပါ။"
    u_pass = user_password.strip()
    if not u_pass: return "⚠️ User VIP Code ရိုက်ထည့်ပါ။"

    days_map = {"Monthly (၁ လ)": 30, "Yearly (၁ နှစ်)": 365}
    days_to_add = days_map.get(plan_type, 30)

    VIP_PASSWORDS = load_vip_database()
    current_time = datetime.datetime.now()
    
    if u_pass in VIP_PASSWORDS:
        try:
            old_expiry = datetime.datetime.strptime(VIP_PASSWORDS[u_pass]["valid_until"], "%Y-%m-%d")
            new_expiry = (old_expiry if old_expiry > current_time else current_time) + datetime.timedelta(days=days_to_add)
        except: new_expiry = current_time + datetime.timedelta(days=days_to_add)
    else: 
        new_expiry = current_time + datetime.timedelta(days=days_to_add)

    VIP_PASSWORDS[u_pass] = {
        "valid_until": new_expiry.strftime("%Y-%m-%d"),
        "plan": plan_type
    }
    save_vip_database(VIP_PASSWORDS)
    return f"✅ အောင်မြင်ပါသည်။ VIP Code [{u_pass}] အား {plan_type} ({new_expiry.strftime('%Y-%m-%d')}) အထိ သတ်မှတ်လိုက်ပါပြီ။"

def check_vip_status_ui():
    db = load_vip_database()
    if not db: return "ယခုလက်ရှိတွင် VIP User မရှိသေးပါ။"
    out = "📋 လက်ရှိ VIP ကုဒ်များစာရင်း -\n\n"
    for k, v in db.items(): 
        plan = v.get('plan', 'လစဉ်')
        out += f"🔑 Code: {k} | 📦 Plan: {plan} | 📅 ကုန်ရက်: {v['valid_until']}\n"
    return out

def verify_user_code(user_code):
    db = load_vip_database()
    u_code = user_code.strip()
    if u_code in db:
        try:
            expiry = datetime.datetime.strptime(db[u_code]["valid_until"], "%Y-%m-%d")
            if expiry >= datetime.datetime.now():
                return True, f"✅ Premium အသုံးပြုနိုင်ပါပြီ (သက်တမ်းကုန်ရက် - {db[u_code]['valid_until']})"
            else:
                return False, "❌ သင်၏ VIP သက်တမ်း ကုန်ဆုံးသွားပါပြီ။"
        except:
            return False, "❌ ကုဒ် စစ်ဆေးရာတွင် အမှားအယွင်းရှိနေပါသည်။"
    return False, "❌ မှားယွင်းနေသော သို့မဟုတ် မရှိသော VIP Code ဖြစ်ပါသည်။"

def format_srt_time(seconds):
    if seconds < 0: seconds = 0
    millis = int(seconds * 1000)
    hours = millis // 3600000
    millis %= 3600000
    minutes = millis // 60000
    millis %= 60000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def segment_myanmar_text(raw_text, max_chars=40):
    for char in ["“", "”", '"', "‘", "’", "'", "--", "—", "…"]:
        raw_text = raw_text.replace(char, " ")
    raw_text = re.sub(r"[ \t]+", " ", raw_text).strip()
    split_pattern = re.split(r'([။၊!?\n]+)', raw_text)
    
    temp_chunks = []
    current_chunk = ""
    for item in split_pattern:
        current_chunk += item
        if any(p in item for p in ['။', '၊', '?', '!', '\n']):
            clean_chunk = current_chunk.strip()
            if len(re.sub(r'[\s၊။!?\-\"\']', '', clean_chunk)) > 0: temp_chunks.append(clean_chunk)
            current_chunk = ""
            
    if current_chunk.strip():
        clean_chunk = current_chunk.strip()
        if len(re.sub(r'[\s၊။!?\-\"\']', '', clean_chunk)) > 0: temp_chunks.append(clean_chunk)
            
    final_segments = []
    for chunk in temp_chunks:
        if len(chunk) <= max_chars: final_segments.append(chunk)
        else:
            sub_words = chunk.split(' ')
            line_buffer = ""
            for word in sub_words:
                if len(line_buffer) + len(word) + 1 <= max_chars: line_buffer += (" " if line_buffer else "") + word
                else:
                    if line_buffer: final_segments.append(line_buffer.strip())
                    if len(word) > max_chars:
                        for i in range(0, len(word), max_chars): final_segments.append(word[i:i+max_chars])
                        line_buffer = ""
                    else: line_buffer = word
            if line_buffer: final_segments.append(line_buffer.strip())
    return final_segments

async def process_voice_generation(
    vip_code, text, surveyed_text, filename, s1_voice, s2_voice, s3_voice,
    style, srt_type, tone, speed, volume, progress=gr.Progress()
):
    is_valid, msg = verify_user_code(vip_code)
    if not is_valid:
        return None, None, None, gr.update(value=msg, visible=True)

    if not text.strip(): return None, None, None, gr.update(value="⚠️ စာသားထည့်သွင်းပါ", visible=True)

    processed_text = text.replace("--", " ").replace("—", " ").replace("…", " ")
    if surveyed_text.strip():
        for line in surveyed_text.strip().split("\n"):
            if "=" in line: key, val = line.split("=", 1); processed_text = processed_text.replace(key.strip(), val.strip())

    voice_map = {"သီဟ (🇲🇲 - ကျား)": "my-MM-ThihaNeural", "နီလာ (🇲🇲 - မ)": "my-MM-NilarNeural"}
    selected_voice = voice_map.get(s1_voice, "my-MM-ThihaNeural")
    base_speed = speed + 20
    speed_rate = f"{'+' if base_speed >= 0 else ''}{base_speed}%"
    volume_rate = f"+{volume}%"

    output_name = filename.strip() if filename.strip() else "Myanmar_TTS"
    output_mp3 = f"{output_name}.mp3"
    output_srt = f"{output_name}.srt"

    max_srt_chars = 40 if srt_type == "TikTok" else 70
    sentences = segment_myanmar_text(processed_text, max_chars=max_srt_chars)
    total_sentences = len(sentences)
    
    if total_sentences == 0: return None, None, None, gr.update(value="❌ စာသား အမှားအယွင်းရှိနေပါသည်", visible=True)

    progress(0.2, desc=f"⏳ အသံပြောင်းလဲနေသည် ({total_sentences} ကြောင်း)...")
    sem = asyncio.Semaphore(15)

    async def fetch_audio(idx, sentence):
        async with sem:
            try:
                communicate = edge_tts.Communicate(text=sentence, voice=selected_voice, rate=speed_rate, volume=volume_rate)
                chunk_audio = bytearray()
                async for msg in communicate.stream():
                    if msg["type"] == "audio": chunk_audio.extend(msg["data"])
                return idx, chunk_audio
            except: return idx, b""

    tasks = [fetch_audio(idx, s) for idx, s in enumerate(sentences)]
    audio_results = await asyncio.gather(*tasks)
    audio_results.sort(key=lambda x: x[0])

    progress(0.7, desc="⚙️ ချိန်ညှိနေပါသည်...")
    combined_audio = AudioSegment.empty()
    subtitles = []
    current_time_sec = 0.0
    natural_pause = AudioSegment.silent(duration=150)

    for idx, chunk_audio in audio_results:
        if not chunk_audio: continue
        temp_file = f"temp_line_{idx}.mp3"
        with open(temp_file, "wb") as f: f.write(chunk_audio)
        try:
            segment = AudioSegment.from_mp3(temp_file)
            nonsilent_ranges = detect_nonsilent(segment, min_silence_len=50, silence_thresh=-50)
            if nonsilent_ranges:
                segment = segment[nonsilent_ranges[0][0]:nonsilent_ranges[-1][1]]
            segment = segment + natural_pause
            duration_sec = len(segment) / 1000.0
            if duration_sec > 0:
                subtitles.append({"start": current_time_sec, "end": current_time_sec + duration_sec, "text": sentences[idx]})
                current_time_sec += duration_sec
                combined_audio += segment
        except: pass
        finally:
            if os.path.exists(temp_file): os.remove(temp_file)

    if len(combined_audio) == 0: return None, None, None, gr.update(value="❌ အသံဖိုင်ထုတ်လုပ်မှု မအောင်မြင်ပါ", visible=True)
    combined_audio.export(output_mp3, format="mp3")

    with open(output_srt, "w", encoding="utf-8-sig") as f:
        for i, sub in enumerate(subtitles, start=1):
            f.write(f"{i}\n{format_srt_time(sub['start'])} --> {format_srt_time(sub['end'])}\n{sub['text'].strip()}\n\n")

    progress(1.0, desc="✅ ပြီးစီးပါပြီ!")
    return output_mp3, output_mp3, output_srt, gr.update(value=msg, visible=True)

def tts_wrapper(vip_code, text, rules_text, filename, s1_voice, s2_voice, s3_voice, style, srt_type, tone, speed, volume):
    return asyncio.run(process_voice_generation(vip_code, text, rules_text, filename, s1_voice, s2_voice, s3_voice, style, srt_type, tone, speed, volume))

# --- GRADIO UI DESIGN ---
# Soft & Modern Premium Theme ကို အသုံးပြုထားသည်
with gr.Blocks(theme=gr.themes.Soft(primary_hue="indigo", secondary_hue="slate")) as demo:
    gr.HTML("""
    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #4F46E5, #06B6D4); color: white; border-radius: 12px; margin-bottom: 25px;">
        <h1 style="margin: 0; font-size: 28px;">🎙️ Myanmar Audio & SRT Studio (Premium)</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">လစဉ်နှင့် နှစ်စဉ် စနစ်သုံး အသံနှင့် စာတန်းထိုး ပြုလုပ်စနစ်</p>
    </div>
    """)
    
    with gr.Row():
        with gr.Column(scale=2):
            # ဝင်ရောက်ရန် VIP Code ထည့်သည့်နေရာ
            vip_code_input = gr.Textbox(label="🔑 Enter VIP Access Code", placeholder="အသုံးပြုရန် သင်၏ လစဉ်/နှစ်စဉ် VIP Code ကို ရိုက်ထည့်ပါ...", type="password")
            status_flash = gr.Markdown(visible=False)
            
            input_text = gr.Textbox(label="✍️ ပြောင်းလဲမည့် မြန်မာစာသား", placeholder="ဤနေရာတွင် စာသားများ ရိုက်ထည့်ပါ...", lines=6)
            
            with gr.Accordion("🔧 အသံထွက်ပြင်ဆင်ရန် (Pronunciation Rules)", open=False):
                rules = gr.TextArea(placeholder="ဥပမာ - ကွန်ပျူတာ = ကွန်ပြူတာ\nဖုန်း = ဖုန်း", lines=3)
                
            file_name = gr.Textbox(label="💾 ဖိုင်အမည်သတ်မှတ်ရန်", value="Myanmar_Audio")
            
        with gr.Column(scale=1):
            voice_choices = ["သီဟ (🇲🇲 - ကျား)", "နီလာ (🇲🇲 - မ)"]
            s1_voice = gr.Dropdown(voice_choices, label="🎙️ Voice ရွေးချယ်ရန်", value="သီဟ (🇲🇲 - ကျား)")
            srt_type = gr.Radio(["TikTok (တို)", "YouTube (ရှည်)"], label="📱 စာတန်းထိုး ပုံစံ", value="TikTok (တို)")
            
            with gr.Accordion("⚙️ အဆင့်မြင့် ဆက်တင်များ", open=False):
                speed = gr.Slider(minimum=-50, maximum=50, value=0, step=1, label="အမြန်နှုန်း (Speed)")
                volume = gr.Slider(minimum=0, maximum=100, value=50, step=1, label="အသံပမာဏ (Volume)")
                tone = gr.Slider(minimum=-50, maximum=50, value=0, step=1, label="Tone", visible=False)
                s2_voice = gr.Dropdown(voice_choices, visible=False, value="နီလာ (🇲🇲 - မ)")
                s3_voice = gr.Dropdown(voice_choices, visible=False, value="သီဟ (🇲🇲 - ကျား)")
                style = gr.Dropdown(["Normal"], visible=False, value="Normal")

            generate_btn = gr.Button("🚀 အသံနှင့် SRT ထုတ်ယူမည်", variant="primary", size="large")

    with gr.Row():
        output_audio = gr.Audio(label="🎧 အသံနားထောင်ရန်")
        output_mp3_file = gr.File(label="📥 MP3 ဒေါင်းလုဒ်")
        output_srt_file = gr.File(label="📝 SRT ဒေါင်းလုဒ်")

    generate_btn.click(
        fn=tts_wrapper,
        inputs=[vip_code_input, input_text, rules, file_name, s1_voice, s2_voice, s3_voice, style, srt_type, tone, speed, volume],
        outputs=[output_audio, output_mp3_file, output_srt_file, status_flash]
    )

    # Admin Panel
    with gr.Accordion("👑 Admin Control Panel (စီမံခန့်ခွဲသူအတွက်)", open=False):
        with gr.Row():
            adm_pass = gr.Textbox(label="🔐 Admin Security Password", type="password")
            u_pass_input = gr.Textbox(label="🔑 ဖန်တီးမည့် VIP Code")
            plan_input = gr.Radio(["Monthly (၁ လ)", "Yearly (၁ နှစ်)"], label="📦 သက်တမ်း အမျိုးအစား", value="Monthly (၁ လ)")
        
        with gr.Row():
            register_btn = gr.Button("✨ VIP Code ထုတ်ပေးမည်", variant="secondary")
            status_btn = gr.Button("📋 လက်ရှိစာရင်းကို စစ်မည်")
            
        admin_output = gr.Textbox(label="📢 Admin လုပ်ဆောင်ချက် ရလဒ်")
        status_output = gr.TextArea(label="ကုဒ်များ စာရင်း", lines=5)
        
        register_btn.click(fn=register_or_renew_vip, inputs=[adm_pass, u_pass_input, plan_input], outputs=admin_output)
        status_btn.click(fn=check_vip_status_ui, inputs=None, outputs=status_output)

demo.launch()
