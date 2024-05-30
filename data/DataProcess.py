import json
import os
import re
import mysql.connector

# 獲取當前腳本文件所在的目錄
current_directory = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_directory, 'taipei-attractions.json')
attractions=[]
with open(file_path, 'r', encoding='utf-8') as file:
    datas= json.load(file)["result"]["results"]
    
    for data in datas:
        img=data["file"]
        
        img_urls = re.findall(r'https://[^\s]+?\.(?:jpg|JPG|png|PNG)', img)
        new_dict={
            "id":data["_id"],
            "name":data["name"],
            "category":data["CAT"],
            "description":data["description"],
            "address":data["address"],
            "transport":data["direction"],
            "mrt": data["MRT"],
            "lat": data["latitude"],
            "lng": data["longitude"],
            "images": img_urls
        }
        attractions.append(new_dict)
# print(attractions[0])
con = mysql.connector.connect(
    host="localhost",
    user="root",
    password="abc31415",
    database="taipeiattractions",
)


for attraction in attractions:
    # if attraction["mrt"] is None:
    #     attraction["mrt"] = "-1"  # 或者使用其他默认值
    with con.cursor() as cursor:
        cursor.execute(\
            "INSERT INTO attractions (name, category, description, address, transport, mrt, lat, lng) \
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", 
            (
                attraction["name"],\
                attraction["category"],\
                attraction["description"],\
                attraction["address"],\
                attraction["transport"],\
                attraction["mrt"],\
                attraction["lat"],\
                attraction["lng"]\
            )
            )
        con.commit()
    
   
    # 插入 Images 表的資料
        attraction_id = cursor.lastrowid 
        for image_url in attraction["images"]:
            cursor.execute("""
            INSERT INTO Images (attraction_id, image_url) 
            VALUES (%s, %s)
            """, (
                attraction_id,
                image_url
            ))
            con.commit()

# 關閉mysql連接
con.close()