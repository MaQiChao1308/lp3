#!/usr/bin/env python3
import os
import csv
import random
from datetime import datetime, timedelta

def generate_mock_data():
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    months = {
        'apr14': (4, 30),
        'may14': (5, 31),
        'jun14': (6, 30)
    }
    
    bases = ['B02512', 'B02598', 'B02617', 'B02682', 'B02764']
    
    print("Verificando datasets em data/...")
    for label, (month, days) in months.items():
        filename = f"uber-raw-data-{label}.csv"
        filepath = os.path.join(data_dir, filename)
        
        if os.path.exists(filepath):
            print(f"Dataset {filename} já existe. Pulando...")
            continue
            
        print(f"Gerando dataset fictício: {filename}...")
        records_count = 1000
        
        with open(filepath, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Date/Time', 'Lat', 'Lon', 'Base'])
            
            start_dt = datetime(2014, month, 1, 0, 0, 0)
            end_dt = datetime(2014, month, days, 23, 59, 59)
            delta_seconds = int((end_dt - start_dt).total_seconds())
            
            timestamps = [
                start_dt + timedelta(seconds=random.randint(0, delta_seconds))
                for _ in range(records_count)
            ]
            timestamps.sort()
            
            for dt in timestamps:
                date_str = dt.strftime('%-m/%-d/%Y %H:%M:%S') if hasattr(dt, 'strftime') else dt.strftime('%m/%d/%Y %H:%M:%S')
                lat = round(40.6 + random.random() * 0.3, 4)
                lon = round(-74.1 + random.random() * 0.3, 4)
                base = random.choice(bases)
                writer.writerow([date_str, lat, lon, base])
                
        print(f"Gerado {filename} com {records_count} registros.")

if __name__ == '__main__':
    generate_mock_data()
