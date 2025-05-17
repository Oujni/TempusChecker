# TempusChecker
TempusChecker will simply check all your times and give you a csv file with the maps name, tier of the map, rank of the map, your time on the map and your rank on the map


# IMPORTANT TO USE - requirements
- You will need Python installed with requests.
  Download Python from the offical website and  and paste this in the teminal:
  "python -m pip install requests" 
  or if that doesn't work 
  "py -m pip install requests"

# Instruction
- Download the files "all_maps_demoman_info.csv" and "all_maps_soldier_info.csv plus the script "Playerrecords.py" and all of them in your folder. (Maps are up to date 17/05/2025)
  Simply run the script and put in your tempus id (Search for yourself on tempus)

Example - https://tempus2.xyz/players/284641/soldier we only need 284641 from this.
Afterwards select the class you want csv to get for you wait for the script to finish (*It can take up to few minutes it need to not overload the api) and done!!

# IMPORTANT NOTES
- The script will not update the csv it created on it's own when you get a pr soo keep that in mind unless you generate a new csv file
- New maps will not be addd automaticly to the maps.csv you will have to generate new one from the file called "MapListSoldier.py" or "MapListDemoman.py"
- The main scipt will create 2 main files one with with your times one with "failed_maps" it will not only show the maps that failed to load your times what that means is you most likelly do not have a time on that map
