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
names={"ai":"AI & công nghệ","world":"Thế giới","vietnam":"Việt Nam","water":"Nước & năng lượng","football":"Arsenal & Premier League","books":"Sách","creator":"Sáng tạo nội dung","trends":"Google Trends"}
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

# Theme clusters are discovery hypotheses, not causal findings or confirmed trends.
theme_defs=[
 {"id":"prices_energy","title":"Giá cả, lạm phát và năng lượng","pattern":r"\binflation\b|inflationary|\boil prices?\b|\bcrude\b|food prices?|energy supply|mortgage rates|\byuan\b|currency|lạm phát|giá lương thực|nhân dân tệ|tỷ giá|năng lượng|giá dầu|giá xăng","reading":"Nhiều tin về giá, tiền tệ hoặc nguồn cung có thể cùng phản ánh áp lực chi phí. Cần kiểm tra chỉ số gốc, mốc thời gian và xem các bài có thực sự nói về cùng một cơ chế hay không.","falsifier":"Bác bỏ giả thuyết nếu dữ liệu gốc không xác nhận diễn biến giá/nguồn cung hoặc các bài nói về thị trường và thời kỳ không liên quan."},
 {"id":"ai_work","title":"AI đi từ năng lực mô hình sang vận hành và công việc","pattern":r"\bagentic\b|\binference\b|\bLLM\b|AI.{0,30}(jobs|work|enterprise|automation|agent|applications)|automation|automate|robotics|tác nhân AI|tự động hóa|việc làm","reading":"Các bài về mô hình, suy luận và công việc có thể cho thấy AI đang được đánh giá theo chi phí triển khai và kết quả vận hành, không chỉ theo khả năng trình diễn. Cần phân biệt nghiên cứu thử nghiệm với sản phẩm đã được triển khai.","falsifier":"Bác bỏ nếu bài chỉ mô tả nghiên cứu hoặc tuyên bố của doanh nghiệp mà không có kết quả triển khai độc lập."},
 {"id":"trade_geopolitics","title":"Thương mại, xung đột và rủi ro chuỗi cung ứng","pattern":r"trade deal|tariff|sanction|\bwar\b|supply risk|shipping|warship|export|import|trade agreement|thuế quan|xuất khẩu|nhập khẩu|chiến sự|chuỗi cung ứng","reading":"Các diễn biến chính trị và thương mại có thể ảnh hưởng đến vận tải, giá đầu vào hoặc quyết định đầu tư. Chưa thể suy ra tác động tới Việt Nam nếu chưa biết tuyến hàng, mặt hàng và mức độ phơi nhiễm.","falsifier":"Bác bỏ nếu chưa có thay đổi chính sách/luồng hàng thực tế hoặc mặt hàng liên quan không gắn với Việt Nam."},
 {"id":"vietnam_business","title":"Việt Nam: chính sách và điều kiện kinh doanh","pattern":r"chính sách|nghị định|thông tư|thuế|doanh nghiệp|đầu tư|xuất khẩu|nhập khẩu|tỷ giá|lãi suất|sản xuất|kinh doanh|thị trường","category":"vietnam","reading":"Chỉ đáng nâng thành tín hiệu khi có văn bản hoặc số liệu gốc, phạm vi áp dụng và nhóm chịu tác động xác định được. Tin kinh doanh đơn lẻ chưa đủ để kết luận xu hướng kinh tế Việt Nam.","falsifier":"Bác bỏ nếu không có văn bản/số liệu gốc hoặc nội dung không tạo thay đổi đáng kể với doanh nghiệp."}
]
themes=[]
for td in theme_defs:
 matched=[]
 for x in items:
  text=s(x.get("title"))+" "+s(x.get("summary"))
  if td.get("category") and s(x.get("category"))!=td["category"]: continue
  if re.search(td["pattern"],text,re.I):
   matched.append(x)
 matched.sort(key=score,reverse=True)
 # Keep independent sources and article links visible; a repeated outlet is not independent confirmation.
 selected=[]; seen=set()
 for x in matched:
  src=s(x.get("source")) or "Nguồn chưa rõ"
  if (s(x.get("url")) or s(x.get("title"))) in seen: continue
  seen.add(s(x.get("url")) or s(x.get("title")))
  selected.append(x)
  if len(selected)>=4: break
 distinct={s(x.get("source")) for x in selected if s(x.get("source"))}
 if len(selected)>=2:
  themes.append({"id":td["id"],"title":td["title"],"status":"Mẫu hình cần kiểm chứng","reading":td["reading"],"falsifier":td["falsifier"],"evidence_count":len(selected),"source_count":len(distinct),"source_note":"Có nhiều nguồn trong batch" if len(distinct)>=2 else "Chỉ một nguồn xuất bản trong batch","evidence":[{"title":s(x.get("title")),"source":s(x.get("source")) or "Nguồn chưa rõ","url":s(x.get("url") or x.get("link")),"published_at":s(x.get("published_at")),"summary":s(x.get("summary"))[:500]} for x in selected]})
coverage=[]
for cat,label in names.items():
 arr=[x for x in items if s(x.get("category"))==cat]
 usable=[x for x in arr if s(x.get("summary")) and s(x.get("url") or x.get("link"))]
 coverage.append({"category":cat,"domain":label,"items":len(arr),"usable":len(usable),"sources":len({s(x.get("source")) for x in usable if s(x.get("source"))})})

out={"schema_version":1,"generated_at":now.isoformat(),"input_generated_at":d.get("generated_at"),"method":"Quy tắc miễn phí: loại trùng URL/tiêu đề, ưu tiên mục có tóm tắt và link nguồn. Không dùng LLM; diễn giải chỉ là khung kiểm chứng, không phải phân tích chuyên gia.","items_in":len(d.get("items",[])),"items_after_dedup":len(items),"signals":signals[:24],"themes":themes,"coverage":coverage,"links":links,"domain_notes":notes,"actions":["Đọc nguồn gốc và xác minh dữ kiện cụ thể trước khi kết luận.","Chỉ nâng ưu tiên khi có nguồn chính thức hoặc nguồn độc lập xác nhận.","Bổ sung feed cho lĩnh vực thiếu dữ liệu; không lấp khoảng trống bằng tin cũ."]}
(R/"data/analysis.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Candidates:",len(out["signals"]),"deduplicated items:",len(items))
