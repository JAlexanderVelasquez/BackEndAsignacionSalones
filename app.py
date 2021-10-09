import os
from flask import Flask, jsonify, request, make_response
import pandas as pd
import re
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.encoders import encode_base64
from datetime import date

pd.set_option('max_columns', None)

app = Flask(__name__)

@app.route('/api')
def api():
    response = jsonify({"message": "api"})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@app.route('/api',methods=['POST'])
def realizarAsignacion():
    with open('Asignacion.csv', "w") as f:
        f.write('')
    with open('outHorarios.txt', "w") as f:
        f.write('')
    with open('outSalones.txt', "w") as f:
        f.write('')
    print("\n\npost realizar asignacion\n")
    userEmail = request.form['userEmail']
    fileP = request.files.get('csvProg')
    dfProg = pd.read_csv(fileP,sep=";",encoding='latin-1')
    fileD = request.files.get('csvDispo')
    dfDispo = pd.read_csv(fileD,sep=";",encoding='latin-1')
    generarDH(dfProg,dfDispo)
    generarDS(dfProg)
    print("Despues de generar los dzn")
    print("Ejecutando modelo horarios")
    os.system('minizinc --solver COIN-BC Horarios.mzn DataHorarios.dzn -o outHorarios.txt')
    print("Despues de minizinc")
    outH = open("outHorarios.txt", "r").read() 
    #print(outH)
    print("Despues de txt")
    matrixC = outH.split('mediodia')[0]
    mediodia = outH.split(';')[1]
    seisAm = outH.split(';')[2]
    open('DataSalones.dzn','a').write(matrixC)
    print(mediodia, seisAm)
    os.system('minizinc --solver COIN-BC Salones.mzn DataSalones.dzn -o outSalones.txt') 
    print("despues de minizinc salones")
    outS = open("outSalones.txt", "r").read() 
    asignacion = outS.split(";")[0]
    salonesLibres = outS.split(";")[1].split("-")[0]
    print(asignacion)
    print(salonesLibres)
    getAsignatures(asignacion,dfProg)
    print("despues de generar asignacion")
    asignacionCsv=pd.read_csv("Asignacion.csv",sep=";",encoding='latin-1')
    print(asignacionCsv)
    enviarEmail("asignacionCsv",userEmail)
    response = make_response(asignacionCsv.to_html())
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

def generarDH(dataProg,dataDispo):
    df=pd.DataFrame(dataProg)
    df=df.sort_values(by=["PLAN","SEMESTRE"])
    dd=pd.DataFrame(dataDispo)
    asig=len(df)    
    doc=len(df.drop_duplicates(subset=['CEDULA']))    
    df2=df.drop_duplicates(subset=['CEDULA']).copy().sort_values(by=["CEDULA"])
    dd = pd.merge(dd, df2[["CEDULA"]], how ='inner', on =['CEDULA'])
    text_file = open("DataHorarios.dzn", "w") 
    text_file.write("diurno = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92};\n")
    text_file.write("nocturno = {13, 14, 15, 16, 29, 30, 31, 32, 45, 46, 47, 48, 61, 62, 63, 64, 77, 78, 79, 80, 93, 94, 95, 96};\n")                               
    text_file.write("H = 96;\n")
    text_file.write("asignaturas = %s;\n" % asig)
    text_file.write("docentes = %s;\n" % doc)
    text_file.write("\nA=[|")
    for i in df.iterrows():
        if(i[1][1].strip().startswith("DIURN")):a="0"
        if(i[1][1].strip().startswith("NOCTUR")):a="1"
        text_file.write(str(i[1][0]))
        text_file.write(", ")
        text_file.write(str(i[1][2]))
        text_file.write(", ")
        text_file.write(str(i[1][3]).strip()[:-1])
        text_file.write(", ")
        text_file.write(str(i[1][5]))
        text_file.write(", ")
        text_file.write(a)
        text_file.write(", ")
        text_file.write(str(i[1][7]))
        text_file.write("\n|")
    text_file.write("];\n")
    Da=[[] for i in range(len(dd))]
    p=-1
    for i in dd.iterrows():
        p+=1
        a=0
        for j in df.iterrows():
            a+=1
            if(i[1][0]==j[1][5]):
                Da[p].append(a)
    Ad=[0]*asig
    text_file.write("Da=[")
    for i in range(len(Da)):
        text_file.write("{ ")
        for j in range(len(Da[i])):
            if(j==len(Da[i])-1):
                text_file.write(str(Da[i][j]))
                Ad[Da[i][j]-1]=i+1
                if(i==len(Da)-1):text_file.write("}\n")
                else:text_file.write("},\n")                
            else:
                text_file.write(str(Da[i][j]))
                text_file.write(", ")
                Ad[Da[i][j]-1]=i+1
    text_file.write("];\nAd=[")
    for i in range(len(Ad)):
        if(i==(len(Ad)-1)):
            text_file.write(str(Ad[i]))
        else:
            text_file.write(str(Ad[i]))
            text_file.write(", ")        
    text_file.write("];\n")    
    text_file.write("D=[|")
    D=np.zeros((96, doc), dtype=bool)
    pro=-1
    for i in dd.iterrows():
        pro+=1
        diasp=[i[1][1],i[1][2],i[1][3],i[1][4],i[1][5],i[1][6]]
        diaact=-1
        for j in diasp:
            diaact+=1
            if(type(j)==str):
                s=re.split(', |,\n|, \n|\n| - |,',j)
                while("" in s):
                    s.remove("")
                while(" " in s):
                    s.remove(" ")
                for k in range(0,len(s),2):
                    if(s[k]!=""):
                        ini=int(s[k][0:2])-6+(diaact*16)
                        fin=int(s[k+1][:-3])-6+(diaact*16)
                        for ifi in range(ini,fin):
                            D[ifi][pro]=True
    for i in range(96):
        for j in range(doc):
            if(D[i][j]):
                text_file.write(str(D[i][j]).lower()+" ")
            else:
                text_file.write(str(D[i][j]).lower())
            if(j<doc-1):text_file.write(",  ")
        text_file.write("\n|")
    text_file.write("];")
    text_file.close()
    print("Data Horarios generado")

def generarDS(dataProg):
    N=96
    S=24
    df1a= dataProg.iloc[:,[3,2,9,8]]
    text_file = open("DataSalones.dzn", "w") 
    text_file.write("Recursos=[SalaSistemas, VideoBean, Ninguno];\n")
    text_file.write("sede=17;\n")
    text_file.write("salones=24;\n")
    text_file.write("Sc=[50,50,35,27,50,50,50,50,50,60,60,60,60,35,40,40,35,45,24,55,55,45,36,50];\n")
    text_file.write("Sr=[SalaSistemas, SalaSistemas, VideoBean,VideoBean,VideoBean, VideoBean,VideoBean, VideoBean,VideoBean, VideoBean,VideoBean, VideoBean,VideoBean, VideoBean,VideoBean, VideoBean,VideoBean, VideoBean,VideoBean, VideoBean,VideoBean, VideoBean,VideoBean, SalaSistemas];\n")
    text_file.write("N=96;\n")
    text_file.write("ini=1;\n")
    text_file.write("fin= %s;\n" % len(df1a))
    text_file.write("Asig= %s ;\n" % len(df1a))
    s="Ar=["
    for row in df1a["SALON"]:
        if(row=="SALA"):
            s+="SalaSistemas,"
        else:
            s+="VideoBean,"
    s=s[:-1]
    s+="];\n"
    text_file.write(s)
    s="Ae=["
    for row in df1a["CUPO"]:
        s+=str(row)
        s+=","
    s=s[:-1]
    s+="];\n"
    text_file.write(s)
    text_file.write("\nSAI=[|")
    for i in range(N):
        for j in range(S):
            if(j==S-1):
                text_file.write("0 ")
            else:
                text_file.write("0, ")
        text_file.write("\n|")
    text_file.write("];")
    text_file.write("\n")
    text_file.close()
    print("Data Salones generado")

def obtenerHoras(posI,posJ,matrix):
    dias = ["LUNES","MARTES","MIERCOLES","JUEVES","VIERNES","SABADO"]
    num = matrix[posI][posJ]
    dia = dias[posI // 16]
    horaInicio = posI % 16 + 6
    horaInicio = str(horaInicio) + ":00" if (horaInicio < 18) else  str(horaInicio) + ":20"
    salon = "Sala de sistemas " + str(posJ % 23 + 1)  if (posJ % 23 == 0 or posJ == 1) else (posJ + 1) % 17 
    while (matrix[posI][posJ] == num and num != 0):
        posI += 1
        if(posI == 96):
            posI-=1
            break
    horaFin = posI % 16 + 6
    horaFin = str(horaFin) + ":20" if (horaFin > 18) else  str(horaFin) + ":00"
    sede = "Principe" if(posJ < 17) else "Villa campestre"
    return (num,dia,horaInicio,horaFin,salon,sede)

def getAsignatures(matrix,progCsv):
    strMatrix = matrix[6:-2].split('\n|')
    for i in range(len(strMatrix)):
        strMatrix[i] = strMatrix[i].split(', ')
        for j in range(len(strMatrix[i])):
            strMatrix[i][j] = int(strMatrix[i][j])
    materiasHoras = []
    for i in range(len(strMatrix)):
        for j in range(len(strMatrix[i])):
            if(strMatrix[i][j]!=0):
                if(i==0 or strMatrix[i][j] != strMatrix[i-1][j]):
                    materiasHoras.append(obtenerHoras(i,j,strMatrix))
    data = progCsv.copy()
    data["SEDE"] = None
    data["DIA"] = None
    data["ENTRADA"] = None
    data["SALIDA"] = None
    pos = 0
    for i in materiasHoras:
        if(data.at[i[0]-1,"DIA"] != None):
            pos = len(data.index)
            data.loc[pos] = data.iloc[i[0]-1]
            data.at[i[0]-1,"SALON"] =i[4]
            data.at[i[0]-1,"DIA"] = i[1]
            data.at[i[0]-1,"ENTRADA"] = i[2]
            data.at[i[0]-1,"SALIDA"] = i[3]
            data.at[i[0]-1,"SEDE"] = i[5]
        data.at[i[0]-1,"SALON"] =i[4]
        data.at[i[0]-1,"DIA"] = i[1]
        data.at[i[0]-1,"ENTRADA"] = i[2]
        data.at[i[0]-1,"SALIDA"] = i[3]
        data.at[i[0]-1,"SEDE"] = i[5]
    data.to_csv('Asignacion.csv', index=False ,sep=";",mode='w')



def enviarEmail(asignacion, email): 
    print("enviar email",email)
    if(email == None):
        email = 'AsignacionSalones@gmail.com'
    # Reemplaza estos valores con tus credenciales de Google Mail
    username = 'AsignacionSalones@gmail.com'
    password = 'AsignacionUnivalle2020'
    remitente = 'AsignacionSalones@gmail.com'
    destinatario = email 
    asunto = "Resultado de la asignacion de salones solicitada el " + date.today().strftime("%d/%m/%Y")
    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"]=asunto
    mensaje["From"]=remitente
    mensaje["To"]=destinatario
    html = f"""
    <html>
    <body>
    Hola! {destinatario} <br/> <br/> 
    Este es un e-mail enviando de manera automatica, por favor <b>NO RESPONDER</b>
    se adjunta el resultado de las asignacion de salones.<br/> <br/> 
    <b>Importante</b><br/>
    Si no hay un archivo excel adjunto con la asignacion correspondiente porfavor revise los csv que proporciono
    como programacion academica y disponibilidad docente, despues vuelva a enviar una solicitud desde la pagina web.
    </body>
    </html>
    """
    parte_html = MIMEText(html,"html")
    mensaje.attach(parte_html)
    try: 
        server = smtplib.SMTP('smtp.gmail.com: 587')
        server.starttls()
        server.login(username, password)
        archivo = 'Asignacion.csv'
        if (asignacion!="ERROR"):
            adjunto = MIMEBase('text', 'x-comma-separated-values')
            adjunto.set_payload(open(archivo, "rb").read())
            encode_base64(adjunto)
            adjunto.add_header('Content-Disposition', 'attachment; filename="%s"' % "Asignacion.csv")
            mensaje.attach(adjunto)
        server.sendmail(remitente, destinatario, mensaje.as_string())
        server.quit()
    except: 
        server.quit()


if __name__ == '__main__':
    app.run(debug=True)