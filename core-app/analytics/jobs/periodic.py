"""
Periodic analytics job: runs run_analytics (Delta -> batch_analytics DB).
Shared entry point for both ECS EventBridge schedule and K8s CronJob.
"""
from run_analytics import main

if __name__ == "__main__":
    main()
