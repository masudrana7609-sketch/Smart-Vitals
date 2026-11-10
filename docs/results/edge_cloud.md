# Edge versus cloud: measurements (10 Nov 2026)

## Could the classifier run at the edge?
`tools/edge_benchmark.py`: the full per-reading decision (last-5 median, model v2, NEWS2-inspired rule), timed over 368 readings.

| Where | Model file | Load | Peak memory | ms per reading (median) | 95th percentile |
|---|---|---|---|---|---|
| Laptop (Apple M4), native Python | 0.38 MB | 0.32 s | 194 MB | 7.5 | 11.0 |
| Container, no limits | 0.38 MB | 0.09 s | 163 MB | 3.9 | 6.9 |
| Container limited to **0.25 CPU and 256 MB** (a rough stand-in for a home gateway, not real hardware) | 0.38 MB | 0.89 s | 163 MB | 4.6 | 84.3 |

At one reading a minute, even 84 ms is negligible: speed is not the problem. **Memory is:** Python with pandas and scikit-learn needs about 160 MB, fine on a phone or gateway but far beyond a wearable's microcontroller (tens to hundreds of KB). Running on the wearable itself would need the trees exported to a small C or ONNX model.

## Data sent
One reading message is **245 bytes** on average: **352 KB per patient per day** at one reading a minute, about 10.6 MB a month, about 3.2 GB a month for 300 patients. Sending only alerts and a 15-minute summary (about 96 messages of roughly 300 bytes) would be about 29 KB a day, **92% less**, but the dashboard would lose minute-by-minute trends (R6, R8) and the cloud could no longer retrain on full data.

## When the network drops
Measured in Docker (`docker_compose.md`): with store-and-forward on the device, a 20-second broker outage lost **0 of 1,777** readings; 723 were delivered late, after reconnecting. Without it, 1,420 were lost. In the cloud design, no alert can be raised during an outage: alerts for readings taken during it arrive once the connection returns (at most the outage length plus about 11 s to reconnect). An edge model could alert locally (on the phone) during the outage.
