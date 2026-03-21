import asyncio
import os
import sys

# 将项目根目录加入 sys.path 以便导入 cuma_cloud
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cuma_cloud.services.ai_agent import trigger_ai_assistant

async def run_agent_job(child_id: int = 1):
    print(f"🚀 Manually triggering Gemini AI agent job for child {child_id}...")
    await trigger_ai_assistant(child_id)
    print("✅ Manual trigger finished.")

if __name__ == '__main__':
    # 允许从命令行传入 child_id 参数，默认是 1
    target_child_id = 1
    if len(sys.argv) > 1:
        try:
            target_child_id = int(sys.argv[1])
        except ValueError:
            print("❌ Invalid child_id. Must be an integer.")
            sys.exit(1)
            
    asyncio.run(run_agent_job(target_child_id))
