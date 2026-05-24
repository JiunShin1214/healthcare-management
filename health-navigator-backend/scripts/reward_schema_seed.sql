ALTER TABLE users
ADD COLUMN points INT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS reward_products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  category VARCHAR(50) NOT NULL,
  brand VARCHAR(100) NOT NULL,
  name VARCHAR(255) NOT NULL,
  price_points INT NOT NULL,
  description TEXT NULL,
  image_url TEXT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS point_transactions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  type VARCHAR(20) NOT NULL,
  amount INT NOT NULL,
  reason VARCHAR(100) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reward_purchases (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  product_id INT NOT NULL,
  price_points INT NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'purchased',
  coupon_code VARCHAR(100) NOT NULL,
  purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES reward_products(id)
);

INSERT INTO reward_products (category, brand, name, price_points, description, is_active)
VALUES
('cafe', '스타벅스', '카페 아메리카노 T', 4500, '모바일 교환권', TRUE),
('cafe', '스타벅스', '카페 라떼 T', 5000, '모바일 교환권', TRUE),
('cafe', '메가커피', '아이스 아메리카노', 2000, '모바일 교환권', TRUE),
('cafe', '컴포즈커피', '아이스 아메리카노', 1800, '모바일 교환권', TRUE),
('convenience', 'GS25', '삼각김밥 교환권', 1200, '편의점 교환권', TRUE),
('convenience', 'CU', '생수 500ml', 1000, '편의점 교환권', TRUE),
('convenience', 'CU', '바나나우유', 1800, '편의점 교환권', TRUE),
('convenience', 'GS25', '컵라면 교환권', 2000, '편의점 교환권', TRUE),
('dining_gift', '아웃백', '아웃백 1만원권', 10000, '외식 상품권', TRUE),
('dining_gift', '빕스', '빕스 1만원권', 10000, '외식 상품권', TRUE),
('dining_gift', '문화상품권', '문화상품권 5천원권', 5000, '모바일 상품권', TRUE),
('health_food', '정관장', '홍삼원 골드', 6000, '건강식품 교환권', TRUE),
('health_food', '한삼인', '홍삼정 스틱', 8000, '건강식품 교환권', TRUE),
('health_food', '천호엔케어', '건강즙 교환권', 7000, '건강식품 교환권', TRUE),
('vitamin', '센트룸', '멀티비타민 교환권', 9000, '비타민/영양제 교환권', TRUE),
('vitamin', 'GNC', '비타민C 교환권', 6000, '비타민/영양제 교환권', TRUE),
('vitamin', '솔가', '비타민D 교환권', 6500, '비타민/영양제 교환권', TRUE),
('donation', '유니세프', '어린이 영양 지원 기부', 5000, '기부 포인트 사용', TRUE),
('donation', '세이브더칠드런', '위기가정 아동 지원 기부', 10000, '기부 포인트 사용', TRUE),
('donation', '굿네이버스', '해외 아동 후원 기부', 30000, '기부 포인트 사용', TRUE),
('cash', '현금환급', '현금환급 5천원', 5000, '현금 교환 신청', TRUE),
('cash', '네이버페이', '네이버페이 5천원권', 5000, '포인트 교환권', TRUE);