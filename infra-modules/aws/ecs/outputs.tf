output "alb_dns_name" { value = aws_lb.main.dns_name }
output "alb_security_group_id" { value = aws_security_group.alb.id }
output "tasks_security_group_id" { value = aws_security_group.tasks.id }
output "service_name" { value = aws_ecs_service.api.name }
output "cluster_name" { value = aws_ecs_cluster.main.name }
output "task_definition_arn" { value = aws_ecs_task_definition.api.arn }
output "spark_task_definition_arn" { value = aws_ecs_task_definition.spark.arn }
output "spark_log_group_name" { value = aws_cloudwatch_log_group.spark.name }
