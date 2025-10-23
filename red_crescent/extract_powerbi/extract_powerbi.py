import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 🔹 إعداد خيارات المتصفح
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# 🔹 إعداد ChromeDriver تلقائيًا
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

# 🔹 فتح تقرير Power BI
url = "https://hcr.pages.gitlab.cartong.org/opsmap/opsmap-yemen/#/"
print("⏳ فتح تقرير Power BI ...")
driver.get(url)

# 🔹 الانتظار حتى تحميل iframe (إذا وُجد)
try:
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, "iframe"))
    )
    iframe = driver.find_element(By.TAG_NAME, "iframe")
    driver.switch_to.frame(iframe)
    print("🔄 تم التبديل إلى iframe.")
except:
    print("ℹ️ لا يوجد iframe أو لم يتم تحميله، الاستمرار بدون تبديل.")

# 🔹 الانتظار حتى ظهور الصفوف
try:
    WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((By.XPATH, "//div[@role='row']"))
    )
except:
    print("⚠️ لم يتم تحميل الصفوف خلال المهلة المحددة.")
    driver.quit()
    exit()

# 🔹 التمرير التلقائي لتحميل كل الصفوف
last_height = driver.execute_script("return document.body.scrollHeight")
while True:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    WebDriverWait(driver, 2).until(lambda d: True)
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
        break
    last_height = new_height

# 🔹 استخراج البيانات من الجدول
rows = driver.find_elements(By.XPATH, "//div[@role='row']")
all_data = []

for row in rows:
    cells = row.find_elements(By.XPATH, ".//div[@role='cell']")
    row_data = [cell.text for cell in cells]
    if any(row_data):
        all_data.append(row_data)

# 🔹 حفظ البيانات في ملف Excel
if all_data:
    num_cols = len(all_data[0])
    columns = [f"Column {i+1}" for i in range(num_cols)]
    df = pd.DataFrame(all_data, columns=columns)
    df.to_excel("PowerBI_Sites_Full.xlsx", index=False)
    print(f"✅ تم حفظ {len(all_data)} صف في PowerBI_Sites_Full.xlsx")
else:
    print("⚠️ لم يتم العثور على بيانات، قد تحتاج تعديل XPATH حسب شكل الجدول.")

driver.quit()