# TensorFlow `tf.data` pipeline: `create_dataset` (CSV + Estimator, in-memory tensors)

> **Purpose:** **`create_dataset`-style pipelines**: (A) **CSV** → `make_csv_dataset` → `map` → train `shuffle`/`repeat` → `prefetch` for **`tf.estimator`**; (B) **in-memory** tensors → `Dataset.from_tensor_slices` → `repeat`/`batch` for tutorials.  
> **Style:** Tables follow [docs/styles/DOCS_TABLE_STYLE.md](../../../styles/DOCS_TABLE_STYLE.md). Diagrams follow [docs/styles/DOCS_MERMAID_DIAGRAM_STYLE.md](../../../styles/DOCS_MERMAID_DIAGRAM_STYLE.md).  
> **Related:** Keras Functional API in [tf_functional_api.md](./tf_functional_api.md).

---

## Training: multiple passes & why the “same” data helps

Training often uses **many passes** over the training set. Each **mini-batch** is a noisy gradient estimate; **shuffling** avoids a fixed order bias. **`repeat()`** on a pipeline means “start over when exhausted,” not “this counts as epoch 2” by itself—**how long** you train is usually set by **steps**, **`fit(epochs=...)`**, or **`max_steps`**.

---

## Revisit: epochs vs `create_dataset` / `repeat()`

- An **epoch** is informally **one full pass** over the training set.
- **`create_dataset`** wires **how** data is read and batched; it does not “count” epochs unless you use something like **`repeat(n)`** with a finite **`n`** (in-memory pattern below).
- CSV + Estimator pattern often uses **`repeat()`** with **no limit** on TRAIN so the trainer never runs dry; **stop** is outside (steps).

---

## In-memory tensors: synthetic `X`, `Y` and `from_tensor_slices`

Build **`X` and `Y` in RAM**, then a **`Dataset`** of pairs `(x_i, y_i)`, then **repeat** and **batch**.

### Step 1 — tensors

```python
N_POINTS = 10
X = tf.constant(range(N_POINTS), dtype=tf.float32)  # [0..9]
Y = 2 * X + 10  # y = 2x + 10 elementwise
```

### Step 2 — `create_dataset`

```python
def create_dataset(X, Y, epochs, batch_size):
    # Must be tf.data.Dataset.from_tensor_slices — NOT tf.data.from_tensor_slices.
    dataset = tf.data.Dataset.from_tensor_slices((X, Y))
    dataset = dataset.repeat(epochs).batch(batch_size, drop_remainder=True)
    return dataset
```

**Easy typo:** `tf.data.from_tensor_slices` raises `AttributeError: module 'tensorflow._api.v2.data' has no attribute 'from_tensor_slices'`. The correct call is **`tf.data.Dataset.from_tensor_slices((X, Y))`**.

| Wrong | Correct |
|:---|:---|
| `tf.data.from_tensor_slices((X, Y))` | `tf.data.Dataset.from_tensor_slices((X, Y))` |

- **`from_tensor_slices`** — zips **`X` and `Y` along axis 0**; each element is one supervised example.
- **`repeat(epochs)`** — repeats the full sequence **`epochs` times** (finite).
- **`batch(..., drop_remainder=True)`** — fixed batch size; **drops** a short last batch.

### vs CSV `create_dataset` (section 1)

| | **In-memory** | **CSV** |
|:---|:---|:---|
| **Source** | Tensors in RAM | Files via `pattern` |
| **Element before extra batch** | Usually **one row** `(x, y)` | **`make_csv_dataset`** often yields **already-batched** dicts |
| **`repeat`** | Often **`repeat(epochs)`** | Train: often **infinite** `repeat()` |

*(Screenshots that lived under `./assets/` before deletion can be re-added manually.)*

---

## 1. The code (reference): CSV + Estimator

`CSV_COLUMNS` and `DEFAULTS` are defined elsewhere.

```python
def create_dataset(pattern, batch_size=1, mode=tf.estimator.ModeKeys.EVAL):
    dataset = tf.data.experimental.make_csv_dataset(
        pattern,
        batch_size,
        CSV_COLUMNS,
        DEFAULTS,
    )
    dataset = dataset.map(features_and_labels)

    if mode == tf.estimator.ModeKeys.TRAIN:
        dataset = dataset.shuffle(buffer_size=1000).repeat()

    dataset = dataset.prefetch(1)
    return dataset
```

**Lazy:** nothing is read until the consumer iterates the dataset.

---

## 2. What each part does (quick map)

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:22%;">Step</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:38%;">API</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:40%;">Role</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Read CSV</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;vertical-align:top;"><code>make_csv_dataset</code></td>
<td style="border:1px solid #D7E0EA;padding:6px;vertical-align:top;">Parse files; **batched** column dicts per step</td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Transform</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;vertical-align:top;"><code>.map(features_and_labels)</code></td>
<td style="border:1px solid #D7E0EA;padding:6px;vertical-align:top;">Batch → <code>(features, labels)</code> for <code>model_fn</code></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Train only</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;vertical-align:top;"><code>shuffle</code> • <code>repeat</code></td>
<td style="border:1px solid #D7E0EA;padding:6px;vertical-align:top;">Randomize • never exhaust on train</td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Overlap I/O</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;vertical-align:top;"><code>prefetch</code></td>
<td style="border:1px solid #D7E0EA;padding:6px;vertical-align:top;">Overlap batch <i>n+1</i> with compute on <i>n</i>; prefer <code>AUTOTUNE</code> in newer code</td>
</tr>
</tbody>
</table>

---

## 3. `make_csv_dataset` already batches

Each dataset element is **one batch** of **`batch_size` rows** (per-column tensors). **`shuffle(buffer_size)`** here shuffles **batches** if applied after batching—not individual rows unless you changed ordering earlier.

---

## 4. `ModeKeys.TRAIN` vs `EVAL`

- **TRAIN:** `shuffle` + `repeat` (infinite stream).
- **EVAL:** single finite pass; no infinite `repeat` (unless you intentionally want looping eval).

---

## 5. `features_and_labels`

Your **`map`** converts each **batch** from CSV columns into what **`Estimator`** (or Keras) expects—typically **`(features_dict_or_tensor, label_tensor)`**.

---

## 6. `model.compile`, optimizer, loss

```python
model.compile(optimizer="adam", loss="mse", metrics=["mae"])
```

**Optimizer** applies **gradients** from **loss**; **Adam** is a common default. Match **loss** to task (e.g. `sparse_categorical_crossentropy` for integer class ids).

---

## 7. `model.fit` and datasets

You can pass a **`tf.data.Dataset`** to **`fit`**. Use **`steps_per_epoch`** when the dataset is **infinite** (e.g. `repeat()` without a cap). **`epochs`** in Keras counts full passes over **`steps_per_epoch`** steps when configured that way.

---

## 8. `model.predict(input_samples, steps=...)`

- **`input_samples`:** data to run **forward only** (no training).
- **`steps`:** number of **batches** to consume; set explicitly if the dataset is **infinite** or repeating.

---

## 9. Takeaways (interview-style)

1. **`tf.data`** builds a **lazy** pipeline; iteration pulls data.  
2. **CSV Estimator pattern:** batch early via **`make_csv_dataset`**, then **`map`**, train with **`shuffle`+`repeat`**, **`prefetch`**.  
3. **In-memory:** **`Dataset.from_tensor_slices((X,Y))`**, then **`repeat(epochs).batch(...)`**; mind **`Dataset.`** prefix.  
4. **Epoch counting** lives in the **trainer**, not magically inside **`repeat()`** for the infinite CSV case.  
5. **`prefetch`** overlaps input pipeline with device work.

---

## Related

- [DOCS_TABLE_STYLE.md](../../../styles/DOCS_TABLE_STYLE.md), [DOCS_MERMAID_DIAGRAM_STYLE.md](../../../styles/DOCS_MERMAID_DIAGRAM_STYLE.md).
