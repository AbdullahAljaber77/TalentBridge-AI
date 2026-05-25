import os
import pandas as pd
from sqlalchemy import create_engine

# استيراد رابط الاتصال من ملف الداتا بيس الخاص بك
from database import DATABASE_URL

# تحديد مسار ملف الـ CSV بدقة
current_dir = os.path.dirname(os.path.abspath(__file__))
csv_file_path = os.path.join(current_dir, "app", "data", "saudi_job_market.csv")
if not os.path.exists(csv_file_path):
    csv_file_path = os.path.join(current_dir, "data", "saudi_job_market.csv")

def ingest_full_dataset():
    print(f"🚀 بدء عملية ضخ كامل الداتا ست من: {csv_file_path}")
    try:
        # إنشاء محرك الاتصال بـ Neon
        engine = create_engine(DATABASE_URL)
        
        # حجم الدفعة الواحدة (قراءة وضخ 5000 وظيفة في كل مرة)
        chunk_size = 5000
        total_rows_inserted = 0
        
        # قراءة الأعمدة المحددة فقط على هيئة دفعات متتالية (Iterator)
        chunks = pd.read_csv(
            csv_file_path, 
            usecols=['job_title', 'company_name', 'description_text'],
            chunksize=chunk_size
        )
        
        column_mapping = {
            'job_title': 'title',
            'company_name': 'company_name',
            'description_text': 'description'
        }
        
        print("⚡ جاري معالجة وضخ البيانات على دفعات متتالية...")
        
        for i, chunk in enumerate(chunks, 1):
            # 1. إعادة تسمية الأعمدة وتنظيف السطور الفارغة للدفعة الحالية
            chunk.rename(columns=column_mapping, inplace=True)
            chunk.dropna(subset=['title', 'company_name'], inplace=True)
            
            # 2. إضافة عمود الحالة الافتراضي للـ Agents
            chunk['status'] = 'Pending_Analysis'
            
            # 3. ضخ الدفعة الحالية إلى السيرفر
            chunk.to_sql('jobs', con=engine, if_exists='append', index=False)
            
            total_rows_inserted += len(chunk)
            print(f"✅ [الدفعة {i}] تم ضخ {len(chunk)} وظيفة بنجاح. (إجمالي المرفوع حتى الآن: {total_rows_inserted})")
            
        print(f"\n🎉 إنجاز عظيم! اكتمل ضخ الداتا ست بالكامل بنجاح تام.")
        print(f"📊 إجمالي عدد الوظائف المرفوعة حية في قاعدة بياناتك: {total_rows_inserted}")
        
    except Exception as e:
        print(f"\n❌ حدث خطأ أثناء ضخ الداتا ست: {e}")

if __name__ == "__main__":
    ingest_full_dataset()