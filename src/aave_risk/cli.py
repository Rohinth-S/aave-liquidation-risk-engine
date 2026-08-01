from .engine import Position,replay,alert
def main():
 for r in replay([Position("demo",10,2000,12000)]): print(r["id"],round(r["health_factor"],2),alert(r))
if __name__=="__main__":main()
