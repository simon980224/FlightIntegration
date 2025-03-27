from . import db

class Airports(db.Model):
    __tablename__ = 'Airports'  # 對應資料庫裡的表名
    
    Airport_Id = db.Column(db.String(10), primary_key=True)
    Airport_Name = db.Column(db.String(100), nullable=False)
    Airport_Name_ZH = db.Column(db.Unicode(100), nullable=True)
    IS_Domestic = db.Column(db.String(10), nullable=False)
    Url = db.Column(db.Text, nullable=True)
    Contact_Info = db.Column(db.Text, nullable=True)
    City_Id = db.Column(db.String(10), nullable=True)
    
    def __repr__(self):
        return f'<Airport {self.Airport_Id}: {self.Airport_Name}>'
    
    def to_dict(self):
        return {
            'Airport_Id': self.Airport_Id,
            'Airport_Name': self.Airport_Name,
            'Airport_Name_ZH': self.Airport_Name_ZH,
            'IS_Domestic': self.IS_Domestic,
            'Url': self.Url,
            'Contact_Info': self.Contact_Info,
            'City_Id': self.City_Id
        }