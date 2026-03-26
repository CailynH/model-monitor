from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import datetime
import uvicorn
import os

app = FastAPI()

# 解决跨域问题，确保前端能访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局缓存
model_cache = []


def get_model_tags(model_id, model_name):
    """
    核心打标函数：根据名称和ID判断模型能力模态
    """
    tags = []
    name_id = (model_id + model_name).lower()

    # 视频能力判断
    if any(x in name_id for x in ['video', 'sora', 'kling', 'luma', 'cogvideo', 'gen-3']):
        tags.append("Video")

    # 语音能力判断
    if any(x in name_id for x in ['audio', 'whisper', 'speech', 'tts', 'stt', 'vocal']):
        tags.append("Audio")

    # 视觉/图片能力判断
    if any(x in name_id for x in ['vision', 'vlm', 'claude-3-5', 'gpt-4o', 'gemini', 'stable-diffusion', 'flux']):
        tags.append("Vision")

    # 默认都有文本能力（除非是纯音频/视频模型，这里做简单处理）
    if not tags or any(x in name_id for x in ['chat', 'instruct', 'gpt', 'claude', 'deepseek', 'llama']):
        tags.insert(0, "Text")

    return tags


def fetch_data():
    print(f"[{datetime.datetime.now()}] 正在抓取国内外模型数据...")
    global model_cache
    new_data = []

    try:
        # 1. 抓取国际数据 (OpenRouter 聚合)
        # 注意：实际使用请在 headers 中加入你的 API Key
        response = requests.get("https://openrouter.ai/api/v1/models")
        if response.status_code == 200:
            intl_raw = response.json().get('data', [])
            for m in intl_raw:
                name = m.get("name", "Unknown")
                mid = m.get("id", "")
                # 价格换算（OpenRouter 原始数据是美元/token，这里转为每百万token的人民币价格）
                price_usd = float(m.get("pricing", {}).get("prompt", 0)) * 1000000

                new_data.append({
                    "name": name,
                    "provider": mid.split('/')[0].capitalize(),
                    "input_price": price_usd * 7.2,  # 自动转人民币
                    "capability": "High" if "gpt-4" in mid or "claude-3" in mid else "Standard",
                    "types": get_model_tags(mid, name)
                })

        # 2. 补充国内特定模型 (如果聚合 API 没覆盖，手动补齐)
        domestic_manual = [
            {"name": "DeepSeek-V3", "provider": "DeepSeek", "input_price": 0.14 * 7.2, "capability": "High",
             "types": ["Text"]},
            {"name": "Kling-Video", "provider": "Kuaishou", "input_price": 0.0, "capability": "High",
             "types": ["Video"]},
            {"name": "SenseVoice", "provider": "SenseTime", "input_price": 0.5, "capability": "Standard",
             "types": ["Audio", "Text"]}
        ]

        model_cache = new_data + domestic_manual
        print(f"成功更新 {len(model_cache)} 个模型数据")

    except Exception as e:
        print(f"更新失败: {e}")


# 定时任务配置
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_data, 'cron', hour=6, minute=0)
scheduler.start()


@app.on_event("startup")
async def startup():
    fetch_data()  # 启动项目时先跑一遍


@app.get("/models")
def get_models():
    return model_cache


if __name__ == "__main__":
    # 这里的 port 会优先读取云服务器的环境变量，如果没有则默认为 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)