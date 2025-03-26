from . import db
from datetime import datetime

class Flights(db.Model):
    __tablename__ = 'Flight'
    
    Flight_Id = db.Column(db.String(50), primary_key=True)
    Airline_Id = db.Column(db.String(50), db.ForeignKey('Airlines.Airline_Id'), nullable=False)
    Scheduled_Departure_Airport_Id = db.Column(db.String(50), db.ForeignKey('Airports.Airport_Id'), nullable=False)
    Scheduled_Arrival_Airport_Id = db.Column(db.String(50), db.ForeignKey('Airports.Airport_Id'), nullable=False)
    Arrival_Departure_Airport_Id = db.Column(db.String(50), db.ForeignKey('Airports.Airport_Id'), nullable=True)
    Arrival_Arrival_Airport_Id = db.Column(db.String(50), db.ForeignKey('Airports.Airport_Id'), nullable=True)
    Scheduled_Departure_Time = db.Column(db.DateTime, nullable=False)
    Scheduled_Arrival_Time = db.Column(db.DateTime, nullable=False)
    Arrival_Departure_Time = db.Column(db.DateTime, nullable=True)
    Arrival_Arrival_Time = db.Column(db.DateTime, nullable=True)
    Status = db.Column(db.String(10), nullable=False)
    
    def __repr__(self):
        return f'<Flight {self.Flight_Id}: {self.Airline_Id} {self.Scheduled_Departure_Airport_Id}-{self.Scheduled_Arrival_Airport_Id}>'
    
    def to_dict(self):
        return {
            'Flight_Id': self.Flight_Id,
            'Airline_Id': self.Airline_Id,
            'Scheduled_Departure_Airport_Id': self.Scheduled_Departure_Airport_Id,
            'Scheduled_Arrival_Airport_Id': self.Scheduled_Arrival_Airport_Id,
            'Arrival_Departure_Airport_Id': self.Arrival_Departure_Airport_Id,
            'Arrival_Arrival_Airport_Id': self.Arrival_Arrival_Airport_Id,
            'Scheduled_Departure_Time': self.Scheduled_Departure_Time.isoformat() if self.Scheduled_Departure_Time else None,
            'Scheduled_Arrival_Time': self.Scheduled_Arrival_Time.isoformat() if self.Scheduled_Arrival_Time else None,
            'Arrival_Departure_Time': self.Arrival_Departure_Time.isoformat() if self.Arrival_Departure_Time else None,
            'Arrival_Arrival_Time': self.Arrival_Arrival_Time.isoformat() if self.Arrival_Arrival_Time else None,
            'Status': self.Status
        }