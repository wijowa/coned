'''
Created on Apr 5, 2012

ConedBill is a wrapper class that pulls account energy usage history from an account number.

@contact: w@econofy.com if a particular account number does not work, 
            there are probably nuances in how ConEd displays different account types            

@usage:
    from coned import ConedBill
    cb = ConedBill('############') 
    cb.dict
    cb.json
    cb.csv
    
@todo: 
    Provide an ESPI wrapper to export in ESPI standard XML format directly
        Currently this functionality is provided through django templating on Econofy

@copyright: William Wagner / Econofy 2012
@author: William Wagner
@license: This module is released under the GPL Version 2.  (see attached license)  
You are free to redistribute or modify as long as you keep this copyright notice here.
 
'''

import urllib
import urllib2
import re
import datetime
import time
import json
import uuid


class ConedBill(object):
    history_url = 'https://apps1.coned.com/csol/billhist.asp'
    msc_status_url = 'https://apps1.coned.com/csol/MSC.asp'
    msc_url = 'https://apps1.coned.com/CSOL/MSC_Process.asp' 
    

    rows=[]
    address=None
    account=None
    rownames = ['StartDate', 'EndDate', 'ElectricEnergyUsage','ElectricPowerDemand','MonthlyElectricBill','MonthlyGasUsage','MonthlyGasBill','TotalEnergyBill']
    msc_values={}
    d=None
    
    @property
    def urn(self):
        return 'urn:uuid:%s' % uuid.uuid4()
    @property
    def now(self):
        return datetime.datetime.now().isoformat()
    
    @property
    def private_account(self):
        return self.account

    def __init__(self,account):
        self.account=account
        self.response=self._read_account()
        eb=self._get_account()
        self._read_msc()
        
    def _read_account(self):
        values={'ACCT':self.account,'GOOD':0}
        data = urllib.urlencode(values)
        req = urllib2.Request(self.history_url,data)

        response = urllib2.urlopen(req)
        r = response.read().split('CONTENT FIELD', 1)[1].split('END CONTENT',1)[0]

        return r
    
    def _read_msc(self):
        values = {'ACCT':self.account,'GOOD':0}
        data = urllib.urlencode(values)
        
        req = urllib2.Request(self.msc_status_url,data)

        response = urllib2.urlopen(req)
        r = response.read().split('CONTENT FIELD', 1)[1].split('END CONTENT',1)[0]
        
        self.msc_values={'ACCT':values['ACCT'],'GOOD':0,'SOURCE':'MSC','LOADZONE':'J','SRVCLASS':'001','EPRES':'100'}

        self.msc_values['SOURCE']=r.split('NAME="SOURCE" VALUE="',1)[1].split('">',1)[0]
        self.msc_values['LOADZONE']=r.split('NAME="LOADZONE", VALUE="',1)[1].split('">',1)[0]
        self.msc_values['SRVCLASS']=r.split('NAME="SRVCLASS", VALUE="',1)[1].split('">',1)[0]
        self.msc_values['EPRES']=r.split('NAME="EPRES", VALUE="',1)[1].split('">',1)[0]
        
        
        self.type = r.split('<td align="left">Electric Rate:</td>',1)[1].split('<td align="left">',1)[1].split('</td>',1)[0].strip()
            
        
    def _get_account(self):
        r=self.response
        rowvalue='<td[\w\W]+?><font[\w\W]+?>([\w\W]+?)<\/font>'
        
        address=r.split('Service Address:&nbsp;&nbsp;',1)[1].split('</td>',1)[0]
        
        table=r.split('Total Bill Amt',1)[1].split('<tr>',1)[1].split('</table>',1)[0]
        rows = []   
        for row in table.split('</tr>')[0:-1]:
            myrow=[]
            for v in row.split('</td>'):
                try:
                    val = re.search(rowvalue,v).groups(0)[0]
                    val = re.sub('[\$,]', '', val)
                    myrow.append(val)
                except AttributeError:
                    pass
            rows.append(myrow)
            
        self.rows=rows
        self.address=address
        return self
    
    def _get_supply_charge(self,datefrom,dateto):
        
        values=self.msc_values
        values['FROMDATE']=datefrom
        values['TODATE']=dateto
             


        data = urllib.urlencode(values)
        req = urllib2.Request(self.msc_url,data)

        response = urllib2.urlopen(req)
        r = response.read().split('CONTENT FIELD', 1)[1].split('END CONTENT',1)[0]
        
        return r.split('<b>Supply Charge</b>',1)[1].split('SIZE="2">',1)[1].split('</font>',1)[0]
        
    
    
    @property
    def dict(self):
        eb = self
        if(eb.d == None):
            d={'Account':eb.account,'Address':eb.address,'Type':eb.type,'History':[],'Start':0,'Duration':0}
            rrows = eb.rows
            rrows.reverse()
            for r in rrows:
                try:
                    sd = r[0].split('/')
                    ed = r[1].split('/')
                    startdate = datetime.date(month=int(sd[0]),day=int(sd[1]),year=int(sd[2]))
                    enddate = datetime.date(month=int(ed[0]),day=int(ed[1]),year=int(ed[2]))
                    days=(enddate-startdate).days      
                    seconds = days*24*3600
                    start = int(time.mktime(startdate.timetuple()))
                    
                    supply = round(float(eb._get_supply_charge(r[0],r[1]))/100.0,4)
                    
                    try:
                        kwh=int(round(float(''.join(r[2].split(',')))))
                        daily=round(kwh/float(days))
                        power=round(kwh/float(days*24.0)*1000.0)
    
                        delivery = round(float(r[7])/kwh,4)
                        total_bill = round((supply+delivery)*kwh,2)
                    except ValueError:
                        #data not available in this interval
                        kwh=None
                        daily=None
                        power=None
                        delivery = None
                        total_bill=None
                    
                    if (d['Start']==0):
                        d['Start']=start
                        
                    d['Duration']+=seconds
                    
                    d['History'].append({'StartDate':r[0],'EndDate':r[1],'Start':start,'Duration':seconds,'Usage':kwh,'DurationDays':days,
                                         'Daily':daily,'Power':power,'SupplyCharge':supply,'DeliveryCharge':delivery,'TotalBill':total_bill})
                    
                except IndexError:
                    pass

            eb.d=d
            return d
        else:
            return eb.d
        
    @property    
    def json(self):
        return json.dumps(self.dict)
    
    @property
    def csv(self):
        s=','.join(self.rownames)
        
        for r in self.rows:
            s="%s\n%s" % (s,','.join(r))
        return s
    
            
