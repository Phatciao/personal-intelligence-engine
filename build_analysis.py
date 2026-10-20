#!/usr/bin/env python3
"""Free, transparent evidence-linked shortlist. No LLM or paid API."""
import json,re
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parent
d=json.loads((R/"data/latest.json").read_text(encoding="utf-8")); items=d.get("items",[])
def s(x): return re.sub(r"\s+"," ",str(x or "")).strip()
def words(x): return set(re.findall(r"[a-zA-ZÀ-ỹ0-9]{4,}",s(x).lower()))-set("that this with from have were will they their about into over after said says what when where which".split())
def dt(x):
 try:return datetime.fromisoformat(str(x).replace("Z","+00:00"))
 except:return None
now=datetime.now(timezone.utc); unique={}
for x in items:
 t=s(x.get("title")); u=re.sub(r"[?#].*$","",s(x.get("url") or x.get("link"))).rstrip("/").lower()
 if not t:continue
 k=u or " ".join(t.lower().split())
 if k not in unique or len(s(x.get("summary")))>len(s(unique[k].get("summary"))):unique[k]=x
items=list(unique.values())
names={"AI":"AI & công nghệ","world":"Thế giới","Vietnam":"Việt Nam","water":"Nước & năng lượng","football":"Arsenal & Premier League","books":"Sách","creator":"Sáng tạo nội dung","trends":"Google Trends"}
groups={}
for x in items:groups.setdefault(s(x.get("category")) or "other",[]).append(x)
def score(x):
 summary=s(x.get("summary")); d=dt(x.get("published_at")); age=(now-d).total_seconds()/3600 if d else 99999
 return min(25,len(summary)//30)+(7 if s(x.get("url") or x.get("link")).startswith("http") else 0)+(5 if age<24 else 2 if age<72 else 0)-(12 if not summary else 0)-(12 if "google_trends"==x.get("signal_source_type") else 0)
signals=[]
for cat,arr in groups.items():
 arr=[x for x in arr if s(x.get("summary")) and s(x.get("url") or x.get("link")) and x.get("signal_source_type")!="google_trends"]
 arr.sort(key=score,reverse=True); chosen=[]
 for x in arr:
  wx=words(x.get("title"))
  if any(len(wx&words(y.get("title")))/max(1,len(wx|words(y.get("title"))))>.75 for y in chosen):continue
  chosen.append(x)
  if len(chosen)==3:break
 for x in chosen:
  signals.append({"domain":names.get(cat,cat),"category":cat,"title":s(x.get("title")),"summary":s(x.get("summary"))[:1200],"source":s(x.get("source")) or "Nguồn chưa ghi","url":s(x.get("url") or x.get("link")),"published_at":s(x.get("published_at")),"confidence":"Thấp–trung bình","facts":"Tóm tắt do feed cung cấp; cần đối chiếu với bài gốc.","interpretation":"Chưa đủ cơ sở để kết luận mức độ tác động chỉ từ một mục RSS.","why":"Được đưa vào danh sách kiểm tra vì có tóm tắt và đường dẫn nguồn.","next":"Mở bài gốc, kiểm tra số liệu/ngày/phạm vi và tìm nguồn độc lập trước khi nâng mức ưu tiên.","score":score(x)})
signals.sort(key=lambda x:x["score"],reverse=True)
links=[]
for i,a in enumerate(signals):
 for b in signals[i+1:]:
  common=words(a["title"]+" "+a["summary"])&words(b["title"]+" "+b["summary"])
  if a["category"]!=b["category"] and len(common)>=2:
   links.append({"a":a["title"],"b":b["title"],"terms":sorted(common)[:6],"note":"Trùng từ khóa là mối liên hệ cần kiểm chứng, không chứng minh quan hệ nhân quả."})
  if len(links)>=8:break
 if len(links)>=8:break
notes=[]
for cat,label in names.items():
 n=sum(1 for x in groups.get(cat,[]) if s(x.get("summary")) and x.get("signal_source_type")!="google_trends")
 if n<2:notes.append({"domain":label,"status":"Thiếu dữ liệu","note":f"Chỉ {n} mục có tóm tắt dùng được; không tạo kết luận mạnh."})
out={"schema_version":1,"generated_at":now.isoformat(),"input_generated_at":d.get("generated_at"),"method":"Quy tắc miễn phí: loại trùng URL/tiêu đề, ưu tiên mục có tóm tắt và link nguồn. Không dùng LLM; diễn giải chỉ là khung kiểm chứng, không phải phân tích chuyên gia.","items_in":len(d.get("items",[])),"items_after_dedup":len(items),"signals":signals[:24],"links":links,"domain_notes":notes,"actions":["Đọc nguồn gốc và xác minh dữ kiện cụ thể trước khi kết luận.","Chỉ nâng ưu tiên khi có nguồn chính thức hoặc nguồn độc lập xác nhận.","Bổ sung feed cho lĩnh vực thiếu dữ liệu; không lấp khoảng trống bằng tin cũ."]}
(R/"data/analysis.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Candidates:",len(out["signals"]),"deduplicated items:",len(items))
