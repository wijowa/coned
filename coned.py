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
    It's possible to grab supply charges from Coned's site through a separate ASP service.

@copyright: William Wagner / Econofy 2012
@author: William Wagner
@license: This module is released under the GPL Version 2.  (see attached license)  
You are free to redistribute or modify as long as you keep this copyright notice here.
 
'''

import urllib
import urllib2
import re
import datetime
import json


class ConedBill(object):
    url='https://apps1.coned.com/csol/billhist.asp'
    rows=[]
    address=None
    account=None
    rownames = ['StartDate', 'EndDate', 'ElectricEnergyUsage','ElectricPowerDemand','MonthlyElectricBill','MonthlyGasUsage','MonthlyGasBill','TotalEnergyBill']
    
    def __init__(self,account):
        self.account=account
        self.response=self._read_account()
        eb=self._get_account()
        
    def _read_account(self):

        values={'ACCT':self.account,'GOOD':0}
        data = urllib.urlencode(values)
        req = urllib2.Request(self.url,data)
        response = urllib2.urlopen(req)
        r = response.read().split('CONTENT FIELD', 1)[1].split('END CONTENT',1)[0]

        return r

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

    @property
    def dict(self):
        eb = self
        d={'Account':eb.account,'Address':eb.address,'History':[]}
        for r in eb.rows:
            try:
                sd = r[0].split('/')
                ed = r[1].split('/')
                startdate = datetime.date(month=int(sd[0]),day=int(sd[1]),year=int(sd[2]))
                enddate = datetime.date(month=int(ed[0]),day=int(ed[1]),year=int(ed[2]))
                days=(enddate-startdate).days             
                try:
                    kwh=round(float(''.join(r[2].split(','))))
                    daily=round(kwh/float(days))
                    power=round(kwh/float(days*24.0)*1000.0)
                except ValueError:
                    #data not available in this interval
                    kwh=None
                    daily=None
                    power=None

                d['History'].append({'StartDate':r[0],'EndDate':r[1],'Duration':days,'kWh':kwh,'USD':r[7],
                                     'Daily':daily,'Power':power})
                
            except IndexError:
                pass
        return d
    
    @property    
    def json(self):
        return json.dumps(self.dict)
    
    @property
    def csv(self):
        s=','.join(self.rownames)
        
        for r in self.rows:
            s="%s\n%s" % (s,','.join(r))
        return s
    
            
        