import argparse
from app.db.session import SessionLocal
from app.services.integration_worker import run_once

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--limit',type=int,default=25); args=parser.parse_args()
    with SessionLocal() as db: print(run_once(db,max(1,min(args.limit,100))))
if __name__=='__main__': main()
