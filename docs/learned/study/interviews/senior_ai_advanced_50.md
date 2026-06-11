# Senior AI Engineer — Advanced Technical Interview (50 Questions)

<table style="width:100%; border-collapse:collapse;">
<thead><tr>
<th style="background:#2F6FAD;color:white;padding:8px;">#</th>
<th style="background:#2F6FAD;color:white;padding:8px;">Question</th>
<th style="background:#2F6FAD;color:white;padding:8px;">Answer</th>
<th style="background:#2F6FAD;color:white;padding:8px;">References</th>
</tr></thead><tbody>
<tr><td>1</td><td>How does backpropagation work at a high level?</td><td>Backpropagation computes gradients via chain rule from output to input. In large systems, efficient autodiff and memory optimization (checkpointing) are critical for scaling training.</td><td>https://pytorch.org/docs/stable/index.html<br>https://www.tensorflow.org/guide</td></tr>
<tr><td>2</td><td>What is gradient clipping and why is it used?</td><td>Gradient clipping limits gradient magnitude to prevent exploding gradients, especially in RNNs or deep transformers. It stabilizes training but may slow convergence.</td><td>https://pytorch.org/docs/stable/index.html<br>https://www.tensorflow.org/guide</td></tr>
<tr><td>3</td><td>Explain attention mechanism complexity.</td><td>Standard attention is O(n^2) in sequence length, making long-context expensive. Techniques like sparse attention or linear attention reduce cost.</td><td>https://pytorch.org/docs/stable/index.html<br>https://www.tensorflow.org/guide</td></tr>
<tr><td>4</td><td>What is KV cache in LLM inference?</td><td>KV cache stores past key/value tensors to avoid recomputation in autoregressive decoding, dramatically reducing latency for long sequences.</td><td>https://github.com/triton-inference-server/server<br>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>5</td><td>How does distributed training work?</td><td>Data parallel splits batches across GPUs; model parallel splits model itself. Communication overhead (AllReduce) becomes bottleneck.</td><td>https://pytorch.org/docs/stable/index.html<br>https://developer.nvidia.com/cuda-zone</td></tr>
<tr><td>6</td><td>What is parameter server vs AllReduce?</td><td>Parameter server centralizes weights; AllReduce synchronizes gradients across workers. AllReduce is more common in modern GPU clusters.</td><td>https://pytorch.org/docs/stable/index.html<br>https://developer.nvidia.com/cuda-zone</td></tr>
<tr><td>7</td><td>Explain GPU memory bottlenecks.</td><td>Limited VRAM constrains batch size and model size. Techniques: gradient checkpointing, mixed precision, offloading.</td><td>https://developer.nvidia.com/cuda-zone<br>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>8</td><td>What is mixed precision training?</td><td>Uses FP16/BF16 to reduce memory and improve throughput while maintaining accuracy via loss scaling.</td><td>https://developer.nvidia.com/cuda-zone<br>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>9</td><td>What is Triton inference server?</td><td>A high-performance inference server supporting multiple frameworks and dynamic batching, widely used in production ML.</td><td>https://github.com/triton-inference-server/server</td></tr>
<tr><td>10</td><td>Explain vector similarity search indexing.</td><td>Indexes like IVF, HNSW trade recall vs speed. FAISS is widely used for billion-scale vector search.</td><td>https://github.com/facebookresearch/faiss</td></tr>
<tr><td>11</td><td>What is ANN vs exact search?</td><td>Approximate nearest neighbor sacrifices exactness for speed, essential for large-scale retrieval systems.</td><td>https://github.com/facebookresearch/faiss</td></tr>
<tr><td>12</td><td>How does sharding work in vector DB?</td><td>Data split across nodes; requires routing queries and merging results. Balancing latency and recall is key.</td><td>https://github.com/facebookresearch/faiss</td></tr>
<tr><td>13</td><td>What is streaming data pipeline?</td><td>Processes data continuously (Kafka, Spark Streaming). Enables real-time ML features and monitoring.</td><td>https://kafka.apache.org/documentation/<br>https://spark.apache.org/docs/latest/</td></tr>
<tr><td>14</td><td>Kafka vs RabbitMQ?</td><td>Kafka is log-based, scalable for streaming; RabbitMQ is queue-based, simpler for messaging.</td><td>https://kafka.apache.org/documentation/</td></tr>
<tr><td>15</td><td>What is idempotent producer in Kafka?</td><td>Ensures messages are not duplicated even with retries, important for exactly-once semantics.</td><td>https://kafka.apache.org/documentation/</td></tr>
<tr><td>16</td><td>Explain Spark DAG execution.</td><td>Spark builds DAG of transformations; lazy evaluation optimizes execution plan.</td><td>https://spark.apache.org/docs/latest/</td></tr>
<tr><td>17</td><td>What is data skew in distributed systems?</td><td>Uneven data distribution causes slow tasks. Fix via repartitioning or salting keys.</td><td>https://spark.apache.org/docs/latest/</td></tr>
<tr><td>18</td><td>How does Kubernetes scale ML services?</td><td>Uses HPA based on CPU/GPU/metrics. Requires careful autoscaling to avoid cold starts.</td><td>https://kubernetes.io/docs/home/</td></tr>
<tr><td>19</td><td>What is gRPC vs REST for ML serving?</td><td>gRPC is faster and binary; REST is simpler and widely supported.</td><td>https://grpc.io/docs/</td></tr>
<tr><td>20</td><td>How do you design caching in ML systems?</td><td>Use Redis for feature caching, embedding caching. Must handle invalidation and freshness.</td><td>https://redis.io/docs/</td></tr>
<tr><td>21</td><td>What is cold start problem?</td><td>Initial latency spike when model/container loads. Mitigation: warm pools, preloading.</td><td>https://kubernetes.io/docs/home/</td></tr>
<tr><td>22</td><td>Explain observability stack for ML.</td><td>Use Prometheus for metrics, OpenTelemetry for tracing, logs for debugging.</td><td>https://prometheus.io/docs/introduction/overview/<br>https://opentelemetry.io/docs/</td></tr>
<tr><td>23</td><td>What is tail latency problem?</td><td>High p99 latency due to slowest requests. Critical for user experience.</td><td>https://prometheus.io/docs/introduction/overview/</td></tr>
<tr><td>24</td><td>How do you debug latency spikes?</td><td>Trace dependencies, check queues, resource contention, GC pauses.</td><td>https://opentelemetry.io/docs/<br>https://prometheus.io/docs/introduction/overview/</td></tr>
<tr><td>25</td><td>What is autoscaling trade-off?</td><td>Fast scaling improves latency but increases cost; slow scaling risks overload.</td><td>https://kubernetes.io/docs/home/</td></tr>
<tr><td>26</td><td>Explain circuit breaker pattern.</td><td>Stops cascading failures by cutting off failing services temporarily.</td><td>https://kubernetes.io/docs/home/</td></tr>
<tr><td>27</td><td>What is feature freshness SLA?</td><td>Guarantee that features are up-to-date within a time bound.</td><td>https://airflow.apache.org/docs/</td></tr>
<tr><td>28</td><td>How to ensure reproducible ML experiments?</td><td>Fix seeds, version data/code, containerize environment.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>29</td><td>What is hyperparameter tuning strategy?</td><td>Grid, random, Bayesian. Bayesian is more efficient for large spaces.</td><td>https://docs.ray.io/en/latest/</td></tr>
<tr><td>30</td><td>What is Ray for ML?</td><td>Distributed compute framework for training and serving ML workloads.</td><td>https://docs.ray.io/en/latest/</td></tr>
<tr><td>31</td><td>Explain model quantization trade-offs.</td><td>Reduces size/latency but may reduce accuracy.</td><td>https://onnxruntime.ai/docs/</td></tr>
<tr><td>32</td><td>What is model distillation?</td><td>Training smaller model from larger one to reduce inference cost.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>33</td><td>What is A/B testing in ML?</td><td>Compare models in production via traffic split.</td><td>https://prometheus.io/docs/introduction/overview/</td></tr>
<tr><td>34</td><td>What is online learning?</td><td>Model updates continuously with new data.</td><td>https://spark.apache.org/docs/latest/</td></tr>
<tr><td>35</td><td>Explain reinforcement learning loop.</td><td>Agent interacts, gets reward, updates policy.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>36</td><td>What is reward hacking?</td><td>Model exploits reward function loopholes.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>37</td><td>What is model interpretability?</td><td>Understanding model decisions via SHAP/LIME.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>38</td><td>Explain SHAP values.</td><td>Feature contribution based on game theory.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>39</td><td>What is fairness in ML?</td><td>Ensuring no bias across groups.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>40</td><td>What is adversarial attack?</td><td>Input perturbations that fool model.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>41</td><td>Explain transfer learning.</td><td>Reuse pretrained model for new task.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>42</td><td>What is self-supervised learning?</td><td>Learning from unlabeled data via proxy tasks.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>43</td><td>Explain contrastive learning.</td><td>Learn representations by pulling similar samples together.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>44</td><td>What is curriculum learning?</td><td>Train from easy to hard examples.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>45</td><td>What is catastrophic forgetting?</td><td>Model forgets old tasks when learning new ones.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>46</td><td>Explain multi-task learning.</td><td>Train one model for multiple tasks.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>47</td><td>What is federated learning?</td><td>Train models across decentralized data.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>48</td><td>What is edge ML?</td><td>Deploy models on devices.</td><td>https://onnxruntime.ai/docs/</td></tr>
<tr><td>49</td><td>Explain privacy-preserving ML.</td><td>Use techniques like differential privacy.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
<tr><td>50</td><td>What is homomorphic encryption in ML?</td><td>Compute on encrypted data.</td><td>https://pytorch.org/docs/stable/index.html</td></tr>
</tbody></table>
