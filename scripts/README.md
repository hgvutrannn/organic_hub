# Search Performance Benchmark Script

Script để đo lường và so sánh hiệu năng giữa Elasticsearch và Django ORM search.

## Cài đặt

1. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

2. Đảm bảo Elasticsearch đang chạy (nếu muốn test Elasticsearch):
```bash
docker-compose up -d elasticsearch
# hoặc
docker run -d -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" docker.elastic.co/elasticsearch/elasticsearch:7.17.0
```

## Sử dụng

### Chạy với tham số mặc định:
```bash
python scripts/benchmark_search.py
```

### Chạy với tham số tùy chỉnh:
```bash
python scripts/benchmark_search.py \
  --num-products 2000 \
  --num-stores 20 \
  --num-categories 10 \
  --num-certificates 5 \
  --iterations 20 \
  --output my_report.html \
  --keep-data
```

### Test với số lượng lớn (100K products):
```bash
python scripts/benchmark_search.py \
  --num-products 100000 \
  --num-stores 50 \
  --num-categories 10 \
  --num-certificates 5 \
  --iterations 10
```

**Lưu ý khi test với số lượng lớn:**
- Script sẽ tự động hỏi xác nhận nếu số products >= 50,000
- Thời gian tạo dữ liệu: ~10-30 phút tùy hệ thống
- Thời gian indexing vào Elasticsearch: ~20-60 phút tùy hệ thống
- Yêu cầu: ít nhất 2GB RAM, đủ dung lượng database
- Nếu chỉ muốn test Django ORM, dùng `--skip-indexing`

### Các tham số:

- `--num-products`: Số lượng products cần tạo (mặc định: 1000)
- `--num-stores`: Số lượng stores cần tạo (mặc định: 10)
- `--num-categories`: Số lượng categories cần tạo (mặc định: 5)
- `--num-certificates`: Số lượng certificates cần tạo (mặc định: 3)
- `--iterations`: Số lần lặp lại mỗi test case (mặc định: 10)
- `--output`: Tên file HTML report (mặc định: benchmark_report.html)
- `--keep-data`: Giữ lại test data sau khi benchmark (mặc định: xóa)
- `--skip-indexing`: Bỏ qua indexing vào Elasticsearch (chỉ test Django ORM)

## Kết quả

Script sẽ tạo file HTML report với:
- Summary statistics
- Charts so sánh execution time, memory usage, CPU usage
- Detailed results table với tất cả metrics

## Lưu ý

- Script sẽ tự động tạo và xóa test data (trừ khi dùng `--keep-data`)
- Nếu Elasticsearch không available, script sẽ tiếp tục chạy với Django ORM only
- Script cần quyền truy cập database và có thể mất thời gian để tạo dữ liệu lớn

