# shutr7

Extract shutter count from your Canon R7 camera over USB.

## Usage/example

```bash
# Get shutter count
$ uv run shutr7 count

Camera: Canon.Inc Canon EOS R7
Firmware: 3-1.6.0

Mechanical Shutter: <= 6,000
Total Actuations:   <= 19,000

Life Expectancy: 200,000
Remaining: ~194,000 (97.0%)
Usage: [#---------------------------------------] 3.0%

```

```bash
# JSON output
$ uv run shutr7 count --json

{
  "camera": {
    "manufacturer": "Canon.Inc",
    "model": "Canon EOS R7",
    "firmware_version": "3-1.6.0"
  },
  "shutter": {
    "mechanical_count": 6000,
    "total_count": 19000,
    "life_expectancy": 200000,
    "remaining": 194000,
    "percentage_used": 3.0
  }
}
```

## License

GPLv3 or later. If you need a different license to use in your project, feel free to reach out. 
