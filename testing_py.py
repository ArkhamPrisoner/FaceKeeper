import ipinfo
import pprint

access_token = 'e8943b3e104ea1'
handler = ipinfo.getHandler(access_token)
details = handler.getDetails()
print(details.city)
print(details.loc)
pprint.pprint(details.all)