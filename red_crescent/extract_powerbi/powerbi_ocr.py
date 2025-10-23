import time
import pytesseract
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# إعداد خيارات المتصفح
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")

# تحديد مسار ChromeDriver
service = Service("/usr/local/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

# فتح تقرير Power BI
url = "https://app.powerbi.com/view?r=eyJrIjoiNGUzNzBkOGQtNzEzNC00NTk5LTk2NGMtYzlkNTA5MmM3ZDEyIiwidCI6ImU1YzM3OTgxLTY2NjQtNDEzNC04YTBjLTY1NDNkMmFmODBiZSIsImMiOjh9&amp;disablecdnExpiration=1755477615"
print("⏳ فتح تقرير Power BI ...")
driver.get(url)

# الانتظار حتى تحميل الصفحة
time.sleep(30)

# التقاط صورة للشاشة
screenshot_path = "powerbi_screenshot.png"
driver.save_screenshot(screenshot_path)
print(f"📸 تم حفظ لقطة الشاشة في {screenshot_path}")

# إغلاق المتصفح
driver.quit()

# استخدام OCR لاستخراج النصوص من الصورة
image = Image.open(screenshot_path)
extracted_text = pytesseract.image_to_string(image)

# حفظ النص في ملف
text_output_path = "powerbi_extracted_text.txt"
with open(text_output_path, "w", encoding="utf-8") as f:
    f.write(extracted_text)

print(f"✅ تم استخراج النصوص وحفظها في {text_output_path}")