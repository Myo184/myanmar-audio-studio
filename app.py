import asyncio
import os
import gradio as gr
import edge_tts
from edge_tts import SubMaker

VOICE_MAP = {
    "👨 အမျိုးသားအသံ (Thiha)": "my-MM-ThihaNeural",
    "👩 အမျိုးသမီးအသံ (Nilar)": "my-MM-NilarNeural"
}

def process_tts_and_srt(text, voice_choice, speed_val, volume_val, progress=gr.Progress()):
    if not text.strip():
        return None, None, None, "❌ ကျေးဇူးပြု၍ စာသားတစ်ခုခု ရိုက်ထည့်ပါ!"
        
    audio_path = "output.mp3"
    srt_path = "output.srt"
    
    if os.path.exists(audio_path): os.remove(audio_path)
    if os.path.exists(srt_path): os.remove(srt_path)
    
    progress(0.1, desc="🤖 AI Engine နှင့် ချိတ်ဆက်နေသည်...")
    selected_voice = VOICE_MAP.get(voice_choice, "my-MM-ThihaNeural")
    rate_str = f"{speed_val:+}%"
    volume_str = f"{volume_val:+}%"
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    communicate = edge_tts.Communicate(text, selected_voice, rate=rate_str, volume=volume_str)
    submaker = SubMaker()
    
    progress(0.4, desc="🎙️ မြန်မာအသံဖိုင် (MP3) ကို ဖန်တီးနေသည်...")
    
    async def _generate():
        with open(audio_path, "wb") as fp:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    fp.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)
                    
    loop.run_until_complete(_generate())
    loop.close()
    
    progress(0.8, desc="📝 စာတန်းထိုးဖိုင် (SRT) ကို တွက်ချက်နေသည်...")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(submaker.get_srt())
        
    progress(1.0, desc="✅ လုပ်ဆောင်ချက် အားလုံး ပြီးဆုံးပါပြီ!")
    return audio_path, audio_path, srt_path, "🎉 ပြောင်းလဲခြင်း အောင်မြင်ပါသည်။ အောက်တွင် ဒေါင်းလုဒ်ရယူပါ။"

with gr.Blocks() as demo:
    gr.Markdown("# 🇲🇲 Myanmar Text-to-Speech & SRT Generator Pro")
    gr.Markdown("မြန်မာစာရိုက်ထည့်ပြီး ကျား/မ အသံ၊ အသံအနှေးအမြန်၊ အတိုးအလျှော့ ချိန်ညှိကာ MP3 နှင့် SRT ဖိုင်ကို တစ်ပြိုင်နက် ထုတ်ယူနိုင်ပါသည်။")
    
    with gr.Row():
        with gr.Column():
            input_text = gr.Textbox(label="မြန်မာစာသား ရိုက်ထည့်ရန်", placeholder="ဒီနေရာမှာ စာရိုက်ပါ...", lines=8)
            voice_dropdown = gr.Dropdown(choices=list(VOICE_MAP.keys()), value="👨 အမျိုးသားအသံ (Thiha)", label="အသံအမျိုးအစား ရွေးချယ်ရန် (ကျား / မ)")
            speed_slider = gr.Slider(minimum=-50, maximum=100, value=0, step=5, label="အသံ အနှေး / အမြန် (Speed Rate %)")
            volume_slider = gr.Slider(minimum=-50, maximum=50, value=0, step=5, label="အသံ အတိုး / အလျှော့ (Volume %)")
            submit_btn = gr.Button("🔊 အသံနှင့် SRT ပြောင်းမည်", variant="primary")
            
        with gr.Column():
            status_output = gr.Markdown(value="အဆင်သင့်ဖြစ်ပါပြီ။")
            audio_player = gr.Audio(label="နားဆင်ရန် (Player)", type="filepath")
            
            with gr.Row():
                download_mp3 = gr.File(label="📥 MP3 ဖိုင်ဒေါင်းလုဒ်ရန်")
                download_srt = gr.File(label="📥 SRT စာတန်းထိုးဒေါင်းလုဒ်ရန်")
                
    submit_btn.click(
        fn=process_tts_and_srt,
        inputs=[input_text, voice_dropdown, speed_slider, volume_slider],
        outputs=[audio_player, download_mp3, download_srt, status_output]
    )

if __name__ == "__main__":
    # Railway တွင် port အော်တိုဖတ်နိုင်ရန် os.environ.get သုံးပေးရပါမည်
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
