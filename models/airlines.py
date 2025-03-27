from . import db

class Airlines(db.Model):
    __tablename__ = 'Airlines'  # 對應資料庫裡的表名
    
    Airline_Id = db.Column(db.String(10), primary_key=True)
    Airline_Name = db.Column(db.String(100), nullable=False)
    Airline_Name_ZH = db.Column(db.Unicode(100), nullable=True)
    IS_Domestic = db.Column(db.String(10), nullable=False)
    Url = db.Column(db.Text, nullable=True)
    Contact_Info = db.Column(db.Text, nullable=True)
    
    # 關聯到Flights表
    flights = db.relationship('Flights', backref='airline', lazy=True)
    
    def __repr__(self):
        return f'<Airline {self.Airline_Id}: {self.Airline_Name}>'
    
    def to_dict(self):
        return {
            'Airline_Id': self.Airline_Id,
            'Airline_Name': self.Airline_Name,
            'Airline_Name_ZH': self.Airline_Name_ZH,
            'IS_Domestic': self.IS_Domestic,
            'Url': self.Url,
            'Contact_Info': self.Contact_Info
        }