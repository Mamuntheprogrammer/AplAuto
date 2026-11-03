import mysql.connector    
cnx = mysql.connector.connect(user='root', password='',
                              host='127.0.0.1',
                              database='test')

cursor = cnx.cursor()
cursor.execute("""select distinct Employee from zemp where Employee<>'EM00000000' and Hierarchy_lvl between 2 and 7 and division in (1,2,4)""")
mailer = cursor.fetchall()


style = ''' 
<style>
    body {
        padding: 0px;
        text-align: left;
        color: black;
        line-height: 12 em;
    }
    span {
        font-size: 20px
        font-weight: bold;
        text-align: left;
        color: red;
    }
    .hcaption {
            font-family:Arial Narrow, Helvetica, sans-serif;
           font-size:26px;
           font-weight: bold;
           text-align:center;
           color:#1d03ab;
     }
    .htitle {
            font-family:Arial Narrow, Helvetica, sans-serif;
            padding-top:10px;
           font-size:20px;
           font-weight: bold;
           color:#4682B4
     }
    .htitle2 {
            font-family:Arial Narrow, Helvetica, sans-serif;
            padding-top:10px;
           font-size:9px;
           font-weight: bold;
           color:#4682B4
     }
    
    .footer {
            font-family:Arial Narrow, Helvetica, sans-serif;
            padding-top:10px;
           font-size:12px;
           font-weight: bold;
           color:#4682B4
     }
     .tab_title {
        font-family:Arial Narrow, Helvetica, sans-serif;
           font-size:16px;
           font-weight: bold;
           color:#35077d
     }
      .basic_table {
     
    font-family:Arial Narrow, Helvetica, sans-serif;
        color:#000;
        background:#eaebec;
        margin:0px;
        border:1px solid #000000;
        border-collapse:collapse;
    }
    .basic_table th {
        white-space:nowrap;
        background: #9ebdff;
        border:1px solid #000000;
        padding:2px;
        font-size:12px;
        text-indent:2px;
    }
    .data_table tr:nth-child(odd) {background-color: #f2f2f2;}
    .basic_table tr {
        text-align:left;
        background: #d4ffee;
        padding-left:0px;
        border:1px solid #000000;
    }
    .basic_table td:first-child {
        text-align: left;
        padding-left:2px;
        border-left: 0;
    }
    
    .basic_table td {
        white-space:nowrap;
        border:1px solid #000000;
        font-size:10px;
        text-indent:2px;
    }
    .data_table {
        font-family:Arial Narrow, Helvetica, sans-serif;
        color:#000;
        background:#eaebec;
        margin:0px;
        border:1px solid #000000;
        border-collapse:collapse;
    }
    
    .data_table th {
        white-space:nowrap;
        background: #9ebdff;
        padding:2px;
        font-size:12px;
        border:1px solid #000000;
    }
    
    .data_table tr:nth-child(odd) {background-color: #f2f2f2;}
    .data_table tr {
        text-align:left;
        background: #d4ffee;
        padding-left:0px;
        border:1px solid #000000;
        font-size:10px;
    }
    .data_table td:first-child {
        text-align: left;
        padding-left:2px;
        border-left: 0;
    }
    
    .data_table td {
        border:1px solid #000000;
        text-indent:2px;
        white-space:nowrap;
    }
     </style>
    
    </head>
      <body>
      <P class='hcaption'>Aristopharma ltd.</p>
      <P class='htitle'>Target vs Achievement upto March, 2023 (highest achv% wise) </p>
      <P class='htitle2'>(Figures in Lac tk)</p>
      
      <p  class = 'tab_title'>Basic Info</p> <TABLE class="basic_table">
'''

temp = '''<TR>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
  <TD>{}</TD>
 </TR>
 '''




#  Geting the Basic data

for x in mailer:
    query = """select employee,name,terr,hie,division FROM tvc where employee = '{}' """.format(str(x[0]))
    # print(query)
    cursor.execute(query)
    basic_data = cursor.fetchall()





    # query = """select employee,name,terr,hie,division FROM tvc where employee = '{}' """.format(str(x[0]))


    basic_info = '''
    <TR>
      <TH>Employee</TH>
      <TH>Name</TH>
      <TH>Territory</TH>
      <TH>hierarchy</TH>
      <TH>division</TH>
     </TR>
     <TR>
      <TD>{}</TD>
      <TD>{}</TD>
      <TD>{}</TD>
      <TD>{}</TD>
      <TD>{}</TD>
     </TR>

    </TABLE>
    '''.format(basic_data[0][0],basic_data[0][1],basic_data[0][2],basic_data[0][3],basic_data[0][4])



    smq="""
    select distinct
tvc.employee,
tvc.name,
tvc.plant,
tvc.depot,
tvc.terr,
tvc.jan_tar,
tvc.jan_sld,
tvc.jan_ach,
tvc.feb_tar,
tvc.feb_sld,
tvc.feb_ach,
tvc.mar_tar,
tvc.mar_sld,
tvc.mar_ach,
tvc.apr_tar,
tvc.apr_sld,
tvc.apr_ach,
tvc.may_tar,
tvc.may_sld,
tvc.may_ach,
tvc.jun_tar,
tvc.jun_sld,
tvc.jun_ach,
tvc.junl_tar,
tvc.junl_sld,
tvc.junl_ach,
tvc.aug_tar,
tvc.aug_sld,
tvc.aug_ach,
tvc.sep_tar,
tvc.sep_sld,
tvc.sep_ach,
tvc.oct_tar,
tvc.oct_sld,
tvc.oct_ach,
tvc.nov_tar,
tvc.nov_sld,
tvc.nov_ach,
tvc.dec_tar,
tvc.dec_sld,
tvc.dec_ach,
tvc.tar,
tvc.sld,
tvc.ach,
tvc.year
from tvc right join zemp on tvc.employee = zemp.Employee 
where 
zemp.Level{} = '{}' and tvc.hie=7""".format(basic_data[0][3],str(x[0]),basic_data[0][3])

    cursor.execute(smq)
    sm_data= cursor.fetchall()
    

    if not sm_data:
        sm = ''
    else:
        sm='''
         <p class='tab_title'>SM</p> <TABLE class="data_table">
         <TR>
          <TH>Employee ID</TH>
          <TH>Name</TH>
          <TH>Depot Code</TH>
          <TH>Depot Name</TH>
          <TH>Territory</TH>
          <TH>Jan_Tar</TH>
          <TH>Jan_Sal</TH>
          <TH>Jan_Ach</TH>
          <TH>Feb_Tar</TH>
          <TH>Feb_Sal</TH>
          <TH>Feb_Ach</TH>
          <TH>Mar_Tar</TH>
          <TH>Mar_Sal</TH>
          <TH>Mar_Ach</TH>
          <TH>Apr_Tar</TH>
          <TH>Apr_Sal</TH>
          <TH>Apr_Ach</TH>
          <TH>May_Tar</TH>
          <TH>May_Sal</TH>
          <TH>May_Ach</TH>
          <TH>Jun_Tar</TH>
          <TH>Jun_Sal</TH>
          <TH>Jun_Ach</TH>
          <TH>Jul_Tar</TH>
          <TH>Jul_Sal</TH>
          <TH>Jul_Ach</TH>
          <TH>Aug_Tar</TH>
          <TH>Aug_Sal</TH>
          <TH>Aug_Ach</TH>
          <TH>Sep_Tar</TH>
          <TH>Sep_Sal</TH>
          <TH>Sep_Ach</TH>
          <TH>Oct_Tar</TH>
          <TH>Oct_Sal</TH>
          <TH>Oct_Ach</TH>
          <TH>Nov_Tar</TH>
          <TH>Nov_Sal</TH>
          <TH>Nov_Ach</TH>
          <TH>Dec_Tar</TH>
          <TH>Dec_Sal</TH>
          <TH>Dec_Ach</TH>
          <TH>Tot_Tar</TH>
          <TH>Tot_Sal</TH>
          <TH>Tot_Ach</TH>
         </TR>
         

        '''
        for y in range(len(sm_data)):
            sm+=temp.format(
sm_data[y][0],
sm_data[y][1],
sm_data[y][2],
sm_data[y][3],
sm_data[y][4],
sm_data[y][5],
sm_data[y][6],
sm_data[y][7],
sm_data[y][8],
sm_data[y][9],
sm_data[y][10],
sm_data[y][11],
sm_data[y][12],
sm_data[y][13],
sm_data[y][14],
sm_data[y][15],
sm_data[y][16],
sm_data[y][17],
sm_data[y][18],
sm_data[y][19],
sm_data[y][20],
sm_data[y][21],
sm_data[y][22],
sm_data[y][23],
sm_data[y][24],
sm_data[y][25],
sm_data[y][26],
sm_data[y][27],
sm_data[y][28],
sm_data[y][29],
sm_data[y][30],
sm_data[y][31],
sm_data[y][32],
sm_data[y][33],
sm_data[y][34],
sm_data[y][35],
sm_data[y][36],
sm_data[y][37],
sm_data[y][38],
sm_data[y][39],
sm_data[y][40],
sm_data[y][41],
sm_data[y][42],
sm_data[y][43]

)
        sm+='</TABLE>'

# DSM

    dsmq="""
        select distinct
    tvc.employee,
    tvc.name,
    tvc.plant,
    tvc.depot,
    tvc.terr,
    tvc.jan_tar,
    tvc.jan_sld,
    tvc.jan_ach,
    tvc.feb_tar,
    tvc.feb_sld,
    tvc.feb_ach,
    tvc.mar_tar,
    tvc.mar_sld,
    tvc.mar_ach,
    tvc.apr_tar,
    tvc.apr_sld,
    tvc.apr_ach,
    tvc.may_tar,
    tvc.may_sld,
    tvc.may_ach,
    tvc.jun_tar,
    tvc.jun_sld,
    tvc.jun_ach,
    tvc.junl_tar,
    tvc.junl_sld,
    tvc.junl_ach,
    tvc.aug_tar,
    tvc.aug_sld,
    tvc.aug_ach,
    tvc.sep_tar,
    tvc.sep_sld,
    tvc.sep_ach,
    tvc.oct_tar,
    tvc.oct_sld,
    tvc.oct_ach,
    tvc.nov_tar,
    tvc.nov_sld,
    tvc.nov_ach,
    tvc.dec_tar,
    tvc.dec_sld,
    tvc.dec_ach,
    tvc.tar,
    tvc.sld,
    tvc.ach,
    tvc.year
    from tvc right join zemp on tvc.employee = zemp.Employee 
    where 
    zemp.Level{} = '{}' and tvc.hie=6""".format(basic_data[0][3],str(x[0]))


    cursor.execute(dsmq)
    dsm_data= cursor.fetchall()

    # print(dsm_data)
    

    if not dsm_data:
        dsm = ''
    else:

        dsm='''
        
         <p class='tab_title'>DSM</p> <TABLE class="data_table">
         <TR>
          <TH>Employee ID</TH>
          <TH>Name</TH>
          <TH>Depot Code</TH>
          <TH>Depot Name</TH>
          <TH>Territory</TH>
          <TH>Jan_Tar</TH>
          <TH>Jan_Sal</TH>
          <TH>Jan_Ach</TH>
          <TH>Feb_Tar</TH>
          <TH>Feb_Sal</TH>
          <TH>Feb_Ach</TH>
          <TH>Mar_Tar</TH>
          <TH>Mar_Sal</TH>
          <TH>Mar_Ach</TH>
          <TH>Apr_Tar</TH>
          <TH>Apr_Sal</TH>
          <TH>Apr_Ach</TH>
          <TH>May_Tar</TH>
          <TH>May_Sal</TH>
          <TH>May_Ach</TH>
          <TH>Jun_Tar</TH>
          <TH>Jun_Sal</TH>
          <TH>Jun_Ach</TH>
          <TH>Jul_Tar</TH>
          <TH>Jul_Sal</TH>
          <TH>Jul_Ach</TH>
          <TH>Aug_Tar</TH>
          <TH>Aug_Sal</TH>
          <TH>Aug_Ach</TH>
          <TH>Sep_Tar</TH>
          <TH>Sep_Sal</TH>
          <TH>Sep_Ach</TH>
          <TH>Oct_Tar</TH>
          <TH>Oct_Sal</TH>
          <TH>Oct_Ach</TH>
          <TH>Nov_Tar</TH>
          <TH>Nov_Sal</TH>
          <TH>Nov_Ach</TH>
          <TH>Dec_Tar</TH>
          <TH>Dec_Sal</TH>
          <TH>Dec_Ach</TH>
          <TH>Tot_Tar</TH>
          <TH>Tot_Sal</TH>
          <TH>Tot_Ach</TH>
         </TR>
        '''
        for h in range(0,len(dsm_data)):
            dsm+=temp.format(
        dsm_data[h][0],
        dsm_data[h][1],
        dsm_data[h][2],
        dsm_data[h][3],
        dsm_data[h][4],
        dsm_data[h][5],
        dsm_data[h][6],
        dsm_data[h][7],
        dsm_data[h][8],
        dsm_data[h][9],
        dsm_data[h][10],
        dsm_data[h][11],
        dsm_data[h][12],
        dsm_data[h][13],
        dsm_data[h][14],
        dsm_data[h][15],
        dsm_data[h][16],
        dsm_data[h][17],
        dsm_data[h][18],
        dsm_data[h][19],
        dsm_data[h][20],
        dsm_data[h][21],
        dsm_data[h][22],
        dsm_data[h][23],
        dsm_data[h][24],
        dsm_data[h][25],
        dsm_data[h][26],
        dsm_data[h][27],
        dsm_data[h][28],
        dsm_data[h][29],
        dsm_data[h][30],
        dsm_data[h][31],
        dsm_data[h][32],
        dsm_data[h][33],
        dsm_data[h][34],
        dsm_data[h][35],
        dsm_data[h][36],
        dsm_data[h][37],
        dsm_data[h][38],
        dsm_data[h][39],
        dsm_data[h][40],
        dsm_data[h][41],
        dsm_data[h][42],
        dsm_data[h][43]

        )
        dsm+='</TABLE>'


# RSM

    rsmq="""
        select distinct
    tvc.employee,
    tvc.name,
    tvc.plant,
    tvc.depot,
    tvc.terr,
    tvc.jan_tar,
    tvc.jan_sld,
    tvc.jan_ach,
    tvc.feb_tar,
    tvc.feb_sld,
    tvc.feb_ach,
    tvc.mar_tar,
    tvc.mar_sld,
    tvc.mar_ach,
    tvc.apr_tar,
    tvc.apr_sld,
    tvc.apr_ach,
    tvc.may_tar,
    tvc.may_sld,
    tvc.may_ach,
    tvc.jun_tar,
    tvc.jun_sld,
    tvc.jun_ach,
    tvc.junl_tar,
    tvc.junl_sld,
    tvc.junl_ach,
    tvc.aug_tar,
    tvc.aug_sld,
    tvc.aug_ach,
    tvc.sep_tar,
    tvc.sep_sld,
    tvc.sep_ach,
    tvc.oct_tar,
    tvc.oct_sld,
    tvc.oct_ach,
    tvc.nov_tar,
    tvc.nov_sld,
    tvc.nov_ach,
    tvc.dec_tar,
    tvc.dec_sld,
    tvc.dec_ach,
    tvc.tar,
    tvc.sld,
    tvc.ach,
    tvc.year
    from tvc right join zemp on tvc.employee = zemp.Employee 
    where 
    zemp.Level{} = '{}' and tvc.hie=4""".format(basic_data[0][3],str(x[0]))

    cursor.execute(rsmq)
    rsm_data= cursor.fetchall()
    

    if not rsm_data:
        rsm = ''
    else:

        rsm='''
        

         <p class='tab_title'>RSM</p> <TABLE class="data_table">
         <TR>
          <TH>Employee ID</TH>
          <TH>Name</TH>
          <TH>Depot Code</TH>
          <TH>Depot Name</TH>
          <TH>Territory</TH>
          <TH>Jan_Tar</TH>
          <TH>Jan_Sal</TH>
          <TH>Jan_Ach</TH>
          <TH>Feb_Tar</TH>
          <TH>Feb_Sal</TH>
          <TH>Feb_Ach</TH>
          <TH>Mar_Tar</TH>
          <TH>Mar_Sal</TH>
          <TH>Mar_Ach</TH>
          <TH>Apr_Tar</TH>
          <TH>Apr_Sal</TH>
          <TH>Apr_Ach</TH>
          <TH>May_Tar</TH>
          <TH>May_Sal</TH>
          <TH>May_Ach</TH>
          <TH>Jun_Tar</TH>
          <TH>Jun_Sal</TH>
          <TH>Jun_Ach</TH>
          <TH>Jul_Tar</TH>
          <TH>Jul_Sal</TH>
          <TH>Jul_Ach</TH>
          <TH>Aug_Tar</TH>
          <TH>Aug_Sal</TH>
          <TH>Aug_Ach</TH>
          <TH>Sep_Tar</TH>
          <TH>Sep_Sal</TH>
          <TH>Sep_Ach</TH>
          <TH>Oct_Tar</TH>
          <TH>Oct_Sal</TH>
          <TH>Oct_Ach</TH>
          <TH>Nov_Tar</TH>
          <TH>Nov_Sal</TH>
          <TH>Nov_Ach</TH>
          <TH>Dec_Tar</TH>
          <TH>Dec_Sal</TH>
          <TH>Dec_Ach</TH>
          <TH>Tot_Tar</TH>
          <TH>Tot_Sal</TH>
          <TH>Tot_Ach</TH>
         </TR>
         

        '''
        for b in range(len(rsm_data)):
            rsm+=temp.format(
rsm_data[b][0],
rsm_data[b][1],
rsm_data[b][2],
rsm_data[b][3],
rsm_data[b][4],
rsm_data[b][5],
rsm_data[b][6],
rsm_data[b][7],
rsm_data[b][8],
rsm_data[b][9],
rsm_data[b][10],
rsm_data[b][11],
rsm_data[b][12],
rsm_data[b][13],
rsm_data[b][14],
rsm_data[b][15],
rsm_data[b][16],
rsm_data[b][17],
rsm_data[b][18],
rsm_data[b][19],
rsm_data[b][20],
rsm_data[b][21],
rsm_data[b][22],
rsm_data[b][23],
rsm_data[b][24],
rsm_data[b][25],
rsm_data[b][26],
rsm_data[b][27],
rsm_data[b][28],
rsm_data[b][29],
rsm_data[b][30],
rsm_data[b][31],
rsm_data[b][32],
rsm_data[b][33],
rsm_data[b][34],
rsm_data[b][35],
rsm_data[b][36],
rsm_data[b][37],
rsm_data[b][38],
rsm_data[b][39],
rsm_data[b][40],
rsm_data[b][41],
rsm_data[b][42],
rsm_data[b][43]

)
        rsm+='</TABLE>'


#  AM

    amq="""
        select distinct
    tvc.employee,
    tvc.name,
    tvc.plant,
    tvc.depot,
    tvc.terr,
    tvc.jan_tar,
    tvc.jan_sld,
    tvc.jan_ach,
    tvc.feb_tar,
    tvc.feb_sld,
    tvc.feb_ach,
    tvc.mar_tar,
    tvc.mar_sld,
    tvc.mar_ach,
    tvc.apr_tar,
    tvc.apr_sld,
    tvc.apr_ach,
    tvc.may_tar,
    tvc.may_sld,
    tvc.may_ach,
    tvc.jun_tar,
    tvc.jun_sld,
    tvc.jun_ach,
    tvc.junl_tar,
    tvc.junl_sld,
    tvc.junl_ach,
    tvc.aug_tar,
    tvc.aug_sld,
    tvc.aug_ach,
    tvc.sep_tar,
    tvc.sep_sld,
    tvc.sep_ach,
    tvc.oct_tar,
    tvc.oct_sld,
    tvc.oct_ach,
    tvc.nov_tar,
    tvc.nov_sld,
    tvc.nov_ach,
    tvc.dec_tar,
    tvc.dec_sld,
    tvc.dec_ach,
    tvc.tar,
    tvc.sld,
    tvc.ach,
    tvc.year
    from tvc right join zemp on tvc.employee = zemp.Employee 
    where 
    zemp.Level{} = '{}' and tvc.hie=2""".format(basic_data[0][3],str(x[0]))

    cursor.execute(amq)
    am_data= cursor.fetchall()
    

    if not am_data:
        am = ''
    else:

        am='''
         <p class='tab_title'>AM</p> <TABLE class="data_table">
         <TR>
          <TH>Employee ID</TH>
          <TH>Name</TH>
          <TH>Depot Code</TH>
          <TH>Depot Name</TH>
          <TH>Territory</TH>
          <TH>Jan_Tar</TH>
          <TH>Jan_Sal</TH>
          <TH>Jan_Ach</TH>
          <TH>Feb_Tar</TH>
          <TH>Feb_Sal</TH>
          <TH>Feb_Ach</TH>
          <TH>Mar_Tar</TH>
          <TH>Mar_Sal</TH>
          <TH>Mar_Ach</TH>
          <TH>Apr_Tar</TH>
          <TH>Apr_Sal</TH>
          <TH>Apr_Ach</TH>
          <TH>May_Tar</TH>
          <TH>May_Sal</TH>
          <TH>May_Ach</TH>
          <TH>Jun_Tar</TH>
          <TH>Jun_Sal</TH>
          <TH>Jun_Ach</TH>
          <TH>Jul_Tar</TH>
          <TH>Jul_Sal</TH>
          <TH>Jul_Ach</TH>
          <TH>Aug_Tar</TH>
          <TH>Aug_Sal</TH>
          <TH>Aug_Ach</TH>
          <TH>Sep_Tar</TH>
          <TH>Sep_Sal</TH>
          <TH>Sep_Ach</TH>
          <TH>Oct_Tar</TH>
          <TH>Oct_Sal</TH>
          <TH>Oct_Ach</TH>
          <TH>Nov_Tar</TH>
          <TH>Nov_Sal</TH>
          <TH>Nov_Ach</TH>
          <TH>Dec_Tar</TH>
          <TH>Dec_Sal</TH>
          <TH>Dec_Ach</TH>
          <TH>Tot_Tar</TH>
          <TH>Tot_Sal</TH>
          <TH>Tot_Ach</TH>
         </TR>
         

        '''
        for c in range(len(am_data)):
            am+=temp.format(
am_data[c][0],
am_data[c][1],
am_data[c][2],
am_data[c][3],
am_data[c][4],
am_data[c][5],
am_data[c][6],
am_data[c][7],
am_data[c][8],
am_data[c][9],
am_data[c][10],
am_data[c][11],
am_data[c][12],
am_data[c][13],
am_data[c][14],
am_data[c][15],
am_data[c][16],
am_data[c][17],
am_data[c][18],
am_data[c][19],
am_data[c][20],
am_data[c][21],
am_data[c][22],
am_data[c][23],
am_data[c][24],
am_data[c][25],
am_data[c][26],
am_data[c][27],
am_data[c][28],
am_data[c][29],
am_data[c][30],
am_data[c][31],
am_data[c][32],
am_data[c][33],
am_data[c][34],
am_data[c][35],
am_data[c][36],
am_data[c][37],
am_data[c][38],
am_data[c][39],
am_data[c][40],
am_data[c][41],
am_data[c][42],
am_data[c][43]

)
        am+='</TABLE>'

#  MIO

    mioq="""
        select distinct
    tvc.employee,
    tvc.name,
    tvc.plant,
    tvc.depot,
    tvc.terr,
    tvc.jan_tar,
    tvc.jan_sld,
    tvc.jan_ach,
    tvc.feb_tar,
    tvc.feb_sld,
    tvc.feb_ach,
    tvc.mar_tar,
    tvc.mar_sld,
    tvc.mar_ach,
    tvc.apr_tar,
    tvc.apr_sld,
    tvc.apr_ach,
    tvc.may_tar,
    tvc.may_sld,
    tvc.may_ach,
    tvc.jun_tar,
    tvc.jun_sld,
    tvc.jun_ach,
    tvc.junl_tar,
    tvc.junl_sld,
    tvc.junl_ach,
    tvc.aug_tar,
    tvc.aug_sld,
    tvc.aug_ach,
    tvc.sep_tar,
    tvc.sep_sld,
    tvc.sep_ach,
    tvc.oct_tar,
    tvc.oct_sld,
    tvc.oct_ach,
    tvc.nov_tar,
    tvc.nov_sld,
    tvc.nov_ach,
    tvc.dec_tar,
    tvc.dec_sld,
    tvc.dec_ach,
    tvc.tar,
    tvc.sld,
    tvc.ach,
    tvc.year
    from tvc right join zemp on tvc.employee = zemp.Employee 
    where 
    zemp.Level{} = '{}' and tvc.hie=1""".format(basic_data[0][3],str(x[0]))

    cursor.execute(mioq)
    mio_data= cursor.fetchall()
    

    if not mio_data:
        mio = ''
    else:

        mio='''
         <p class='tab_title'>MIO</p> <TABLE class="data_table">
         <TR>
          <TH>Employee ID</TH>
          <TH>Name</TH>
          <TH>Depot Code</TH>
          <TH>Depot Name</TH>
          <TH>Territory</TH>
          <TH>Jan_Tar</TH>
          <TH>Jan_Sal</TH>
          <TH>Jan_Ach</TH>
          <TH>Feb_Tar</TH>
          <TH>Feb_Sal</TH>
          <TH>Feb_Ach</TH>
          <TH>Mar_Tar</TH>
          <TH>Mar_Sal</TH>
          <TH>Mar_Ach</TH>
          <TH>Apr_Tar</TH>
          <TH>Apr_Sal</TH>
          <TH>Apr_Ach</TH>
          <TH>May_Tar</TH>
          <TH>May_Sal</TH>
          <TH>May_Ach</TH>
          <TH>Jun_Tar</TH>
          <TH>Jun_Sal</TH>
          <TH>Jun_Ach</TH>
          <TH>Jul_Tar</TH>
          <TH>Jul_Sal</TH>
          <TH>Jul_Ach</TH>
          <TH>Aug_Tar</TH>
          <TH>Aug_Sal</TH>
          <TH>Aug_Ach</TH>
          <TH>Sep_Tar</TH>
          <TH>Sep_Sal</TH>
          <TH>Sep_Ach</TH>
          <TH>Oct_Tar</TH>
          <TH>Oct_Sal</TH>
          <TH>Oct_Ach</TH>
          <TH>Nov_Tar</TH>
          <TH>Nov_Sal</TH>
          <TH>Nov_Ach</TH>
          <TH>Dec_Tar</TH>
          <TH>Dec_Sal</TH>
          <TH>Dec_Ach</TH>
          <TH>Tot_Tar</TH>
          <TH>Tot_Sal</TH>
          <TH>Tot_Ach</TH>
         </TR>
         

        '''
        for c in range(len(mio_data)):
            mio+=temp.format(
mio_data[c][0],
mio_data[c][1],
mio_data[c][2],
mio_data[c][3],
mio_data[c][4],
mio_data[c][5],
mio_data[c][6],
mio_data[c][7],
mio_data[c][8],
mio_data[c][9],
mio_data[c][10],
mio_data[c][11],
mio_data[c][12],
mio_data[c][13],
mio_data[c][14],
mio_data[c][15],
mio_data[c][16],
mio_data[c][17],
mio_data[c][18],
mio_data[c][19],
mio_data[c][20],
mio_data[c][21],
mio_data[c][22],
mio_data[c][23],
mio_data[c][24],
mio_data[c][25],
mio_data[c][26],
mio_data[c][27],
mio_data[c][28],
mio_data[c][29],
mio_data[c][30],
mio_data[c][31],
mio_data[c][32],
mio_data[c][33],
mio_data[c][34],
mio_data[c][35],
mio_data[c][36],
mio_data[c][37],
mio_data[c][38],
mio_data[c][39],
mio_data[c][40],
mio_data[c][41],
mio_data[c][42],
mio_data[c][43]

)
        mio+='</TABLE>'

    body2='''

     </body>
    </html>

    '''


    content = style+basic_info+sm+rsm+am+mio+body2

    # for x in range(len(mailer)):
    filename = str(x[0]+".html")
    output = open(filename,"w")
    output.write(content)
    output.close()


cnx.close()