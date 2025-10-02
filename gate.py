import requests

#First Request (payments_methods )
#Copy As Curl And Go To Curl converter and Paste Here
headers = {
    'accept': 'application/json',
    'accept-language': 'en-IN',
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://js.stripe.com',
    'priority': 'u=1, i',
    'referer': 'https://js.stripe.com/',
    'sec-ch-ua': '"Chromium";v="127", "Not)A;Brand";v="99", "Microsoft Edge Simulate";v="127", "Lemur";v="127"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',
}

data = 'type=card&card[number]=5284+9734+4941+1457&card[cvc]=880&card[exp_year]=28&card[exp_month]=05&allow_redisplay=unspecified&billing_details[address][country]=NP&pasted_fields=number%2Cexp&payment_user_agent=stripe.js%2F3ba51c7c33%3B+stripe-js-v3%2F3ba51c7c33%3B+payment-element%3B+deferred-intent&referrer=https%3A%2F%2Fshop.wiseacrebrew.com&time_on_page=89477&client_attribution_metadata[client_session_id]=c442c482-2181-43da-9ac0-781973b8522e&client_attribution_metadata[merchant_integration_source]=elements&client_attribution_metadata[merchant_integration_subtype]=payment-element&client_attribution_metadata[merchant_integration_version]=2021&client_attribution_metadata[payment_intent_creation_flow]=deferred&client_attribution_metadata[payment_method_selection_flow]=merchant_specified&client_attribution_metadata[elements_session_config_id]=ab1272eb-079c-4464-9546-9ee4c5b83332&guid=23889ac7-ff59-45b7-ab25-b3200959849722ab6a&muid=2cca6042-5083-44f4-8df0-567693f6898df62026&sid=9e97e254-896a-464f-b0a5-fd09a5c1af98d0bd22&key=pk_live_51Aa37vFDZqj3DJe6y08igZZ0Yu7eC5FPgGbh99Zhr7EpUkzc3QIlKMxH8ALkNdGCifqNy6MJQKdOcJz3x42XyMYK00mDeQgBuy&_stripe_version=2024-06-20&radar_options[hcaptcha_token]=P1_eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJwZCI6MCwiZXhwIjoxNzU5MzM3NDI3LCJjZGF0YSI6IjFjTjllcUEzdW40Tm10QUdOd2xXK1A4ZWhvWCtYVlB5Q0ZwTGVJZUl2eW8rL3ZIdnJkTmh5TC9Tb0Jtc3BoUEsrZ2hvdk0xWlhvWCtJVHFhcWYzRWMyZnJ0ZEVrcTA2UXpGdkxPb1BaWVR4aWlBUjdJZW9mdmRZeEVZQXJiRC9pWkgwa3Y5OWRpNVhNZGJuWWU5bzN4c2VpVE91R09rS293T295TGxOb0pKRWdZS09Ba0tmdVBkZHdZYUpHeG5vN25GdDBuZ2lHd2hPcTA4OWgiLCJwYXNza2V5IjoiRkZyMVVaWUxnRHQ4endwSXNDMC9vR0JJM0ZqZmRRYUZldGlwQlJQUzlneS9qVklQb2ZRSDhNaUNuUTNTWFlPM25BM1ArVjdCN3ZaVUVRMVJLSGR5WWJTQ2FqL1ZtWEhXdGNDTmNvQnA5ZHVHUldobDk2TENNTFlOc3BRL3htMmFNM252WTBUMFhSLzZwa2RwMjdXTTJPL0lOY1VuOUpOYTNNemQ3T3NhVm1vQ0lvcFEySk5mZmpnZ2U5KzVock5uamNBVlhWV3d4T1VUVEJyZGFvSHh6RXhaemwvQ3M5TXowMzQ3Y2V2a21IUDZ6Zm93cjArSEUrZHZLelZySkIxTnhXaTlDa0MxSzBKMFc5d3MyeTJCM0JCaEZwN2ZjS2RUZmkzaVg2S25CTkZjU0RMblp6WXJvUWo4ZjJhd3pwTzNFeGhSUUFmNlBOeEI3MHhUaWdLMmVTNzJteXMrRm1heVQzTXQzQSttSVVmd2NkcSsvRENxdXdVb0VBYUVJT21jOTVPODZKS0d4QXhYMkFHWW11NmpUdTV0K2VBWXVmL0RMZ0ZKbTNhZWVTK21ENXpWMGRHWjQxYW5sQzNWTjRScjNaV1ZObFk0YmEzcmF0LzdKeFhjeWw4TGlWRnV1T09pQ0xDUVdsQWpMQ2wrRFR3MHVmcFVkV2ZZYnRBdm1OYy9Ucldzbys0YUdIdEV3Qk9mZE5zdFZLM3FUVGhTQUxLakk2ZDV4Ukg0VE11MXZSQ2pLaWVjK1dWVGVtWEZZRGtGaFFuQWdaZUkycjRYTG9Ub09sK203b3dyT3lLd21hUGRkSkpsTm53VEVnYVdLTmI3NXZ0d0dIenRWRWdzNStaZnc3M3RKaWNYSDAreHN6M0xTUzFsRGxQMHNjd2tIWUJSb0tBSnp0OGJHaUJ0Y25SdFJFcDFCSS9Ea0kvdVpaOW5lNStjVUdkTUZjaWJibGV1VDYwUUkyTUZYSk1DdHVBSWdraDlxaFd3cGZSR1JOL3VpVG1mZGd6aGVtMDBKNGlCcVBCemFxR1dHc3NLV0dVU3UvT015a1piYVZRM1YxUW1DS2QvVHNlMXBrTVo0RUxzK1Nnd2RUbTlXVjlxVEFXU2I3TkFmNmxvUmdnZkREdHhkSmtlb3VrdXpSM1dvMmtDUDZPTzhVMkUzb0ZpWnA0dzUreWI2OFJ2QlNqcjhmZlJWeVJiUjAwM1FNSjM2ZTNOOTVqamhJcngvclh5ckhYcVdvVWF6bG1ldi9nZTlBeG5BckVNSWZmR29xeFRqTkJMdXY5dmlrTEF4bmdWRURTYmRpMGdUQ1ZITE02OGlGQ2MxRjBrYXRiWHQ4T1JVVS9lQlVSYnJJU2hRd3BwRVBDT2VSV2ZvZTVZR1ZnL203bnpnS3c1dkJ1U0pIa0xuOUxYdlJmR2tURFRhZm5kYlBkTTF2QlZGQWRWNmVTQVR0WjdNTE1jcWtUR0ppaC8rNEtPOUY1Q2hEL1hWalY3dDFPV01sbFk0K28weUg4QnZLTW9EWCtFMFl6RVlDTW5oSWx6d0Z3V2lZUk42TkVSOC9MajlPaGVEdnU5ZEI3RzUxa2o0aW84eFRSQXc3TEJ6UlZNOHpHWU9EYk0vWWIycmNQUGNpYUc2MDIyOS9uOC85UzRUMVVCSjhnTFk5WjAzWnRhM3VOdnNKYWhZZnF3bXdROElCR3cvMnFrNWhTeGlXZXpxMlRZbWpXcHZLSjRrOGlHWDR5cE1DUnN6ek90RnVzbTY5ODFkQ2pma2FMYUtnOGFIWVYzMlUrejdMNzlkMFE4OGdsQWgyUFlzeXZCaU5kamViWmlJbFpSL3FZeWRlWXdKdnFiekh6cHdTN1dLeXkrZHZRMDlmbkZkQ1JZai9nVHl5bkQvb0IxQXZTWkRJaWpGWHJ6OHFlSjJCUXd4RU5OY0owc0pLSUZ2VEczQVpJVWhPTkxvUHpJL29Yc0FBcW8yOTFoUWl3V1M5RjhLQXZNcnRRaTc5bUtERyswRXRKRWdEaEtOL0F2Uktyb0pGS3A1WjhBRkNQdmpXTE5QMEdobjQvdjdiaC9GUWh3SnU5NjNaYS9aSVpTZUpSclFneTBnZ0t1R0JUdnIvcFBvWUczVm5TbjQ2N0REUXp6UXlPQ1R5VFJjUjB0Y3RoaDZWWndtV3pWVU9Ib29sK1Zqb25sMEJZaC9mZlQ3RUdzbHoxc3pBeVVNQ3Brak4rcHN3amdEN1Zwc1laRWlNZ1g3OHd3Z2FiTStDT3JhY3ZiWmt2NUNjeUF4d0JtQTBadms4cnJvUFhzUzNweW12TEVzUUdkZ0UvbGp0aGY2aE93L2VRT0kwNjg3bE1PdkpaZCtmaU4rTGVxSmhFcm1PNTN2cWdUeU52WFRZUnJFQVdIYXdOZCs5TVp4N0ZGIiwia3IiOiIzODlmNzcxZSIsInNoYXJkX2lkIjozNjI0MDY5OTZ9.iKv7CHDdgCHZEImhOgpI6bVxa2F6MHB_aYP06MHsbSo'

response = requests.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data)




print = (response.json()[id])


#second request (admin ajax )#@diwazz

import requests

cookies = {
    '_ga': 'GA1.1.1382112853.1759337025',
    'sbjs_migrations': '1418474375998%3D1',
    'sbjs_current_add': 'fd%3D2025-10-01%2016%3A28%3A47%7C%7C%7Cep%3Dhttps%3A%2F%2Fshop.wiseacrebrew.com%2F%7C%7C%7Crf%3D%28none%29',
    'sbjs_first_add': 'fd%3D2025-10-01%2016%3A28%3A47%7C%7C%7Cep%3Dhttps%3A%2F%2Fshop.wiseacrebrew.com%2F%7C%7C%7Crf%3D%28none%29',
    'sbjs_current': 'typ%3Dtypein%7C%7C%7Csrc%3D%28direct%29%7C%7C%7Cmdm%3D%28none%29%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Cid%3D%28none%29%7C%7C%7Ctrm%3D%28none%29%7C%7C%7Cmtke%3D%28none%29',
    'sbjs_first': 'typ%3Dtypein%7C%7C%7Csrc%3D%28direct%29%7C%7C%7Cmdm%3D%28none%29%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Cid%3D%28none%29%7C%7C%7Ctrm%3D%28none%29%7C%7C%7Cmtke%3D%28none%29',
    'sbjs_udata': 'vst%3D1%7C%7C%7Cuip%3D%28none%29%7C%7C%7Cuag%3DMozilla%2F5.0%20%28Linux%3B%20Android%2010%3B%20K%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F127.0.0.0%20Mobile%20Safari%2F537.36',
    'mtk_src_trk': '%7B%22type%22%3A%22typein%22%2C%22url%22%3A%22(none)%22%2C%22mtke%22%3A%22(none)%22%2C%22utm_campaign%22%3A%22(none)%22%2C%22utm_source%22%3A%22(direct)%22%2C%22utm_medium%22%3A%22(none)%22%2C%22utm_content%22%3A%22(none)%22%2C%22utm_id%22%3A%22(none)%22%2C%22utm_term%22%3A%22(none)%22%2C%22session_entry%22%3A%22https%3A%2F%2Fshop.wiseacrebrew.com%2F%22%2C%22session_start_time%22%3A%222025-10-01%2016%3A28%3A47%22%2C%22session_pages%22%3A%221%22%2C%22session_count%22%3A%221%22%7D',
    'wordpress_sec_dedd3d5021a06b0ff73c12d14c2f177c': 'khatridiwass%7C1760546682%7CZzZ8FgjdB6raupuJWH5eZGeZ75wyprEIiFOa3L9It2E%7C44a03587a27ea061c3dd6f53ee94600bf2d915bd86f159874e0b51e4d5b8591a',
    'wordpress_logged_in_dedd3d5021a06b0ff73c12d14c2f177c': 'khatridiwass%7C1760546682%7CZzZ8FgjdB6raupuJWH5eZGeZ75wyprEIiFOa3L9It2E%7C79ea1eb0867a45b7193f34e51f2317ec86e8b0fdb84e236c3c204a9ca45a5ab6',
    '__stripe_mid': '2cca6042-5083-44f4-8df0-567693f6898df62026',
    '__stripe_sid': '9e97e254-896a-464f-b0a5-fd09a5c1af98d0bd22',
    'sbjs_session': 'pgs%3D10%7C%7C%7Ccpg%3Dhttps%3A%2F%2Fshop.wiseacrebrew.com%2Faccount%2Fadd-payment-method%2F',
    '_ga_94LZDRFSLM': 'GS2.1.s1759337024$o1$g1$t1759337231$j16$l0$h0',
}

headers = {
    'accept': '*/*',
    'accept-language': 'en-IN',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    # 'cookie': '_ga=GA1.1.1382112853.1759337025; sbjs_migrations=1418474375998%3D1; sbjs_current_add=fd%3D2025-10-01%2016%3A28%3A47%7C%7C%7Cep%3Dhttps%3A%2F%2Fshop.wiseacrebrew.com%2F%7C%7C%7Crf%3D%28none%29; sbjs_first_add=fd%3D2025-10-01%2016%3A28%3A47%7C%7C%7Cep%3Dhttps%3A%2F%2Fshop.wiseacrebrew.com%2F%7C%7C%7Crf%3D%28none%29; sbjs_current=typ%3Dtypein%7C%7C%7Csrc%3D%28direct%29%7C%7C%7Cmdm%3D%28none%29%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Cid%3D%28none%29%7C%7C%7Ctrm%3D%28none%29%7C%7C%7Cmtke%3D%28none%29; sbjs_first=typ%3Dtypein%7C%7C%7Csrc%3D%28direct%29%7C%7C%7Cmdm%3D%28none%29%7C%7C%7Ccmp%3D%28none%29%7C%7C%7Ccnt%3D%28none%29%7C%7C%7Cid%3D%28none%29%7C%7C%7Ctrm%3D%28none%29%7C%7C%7Cmtke%3D%28none%29; sbjs_udata=vst%3D1%7C%7C%7Cuip%3D%28none%29%7C%7C%7Cuag%3DMozilla%2F5.0%20%28Linux%3B%20Android%2010%3B%20K%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F127.0.0.0%20Mobile%20Safari%2F537.36; mtk_src_trk=%7B%22type%22%3A%22typein%22%2C%22url%22%3A%22(none)%22%2C%22mtke%22%3A%22(none)%22%2C%22utm_campaign%22%3A%22(none)%22%2C%22utm_source%22%3A%22(direct)%22%2C%22utm_medium%22%3A%22(none)%22%2C%22utm_content%22%3A%22(none)%22%2C%22utm_id%22%3A%22(none)%22%2C%22utm_term%22%3A%22(none)%22%2C%22session_entry%22%3A%22https%3A%2F%2Fshop.wiseacrebrew.com%2F%22%2C%22session_start_time%22%3A%222025-10-01%2016%3A28%3A47%22%2C%22session_pages%22%3A%221%22%2C%22session_count%22%3A%221%22%7D; wordpress_sec_dedd3d5021a06b0ff73c12d14c2f177c=khatridiwass%7C1760546682%7CZzZ8FgjdB6raupuJWH5eZGeZ75wyprEIiFOa3L9It2E%7C44a03587a27ea061c3dd6f53ee94600bf2d915bd86f159874e0b51e4d5b8591a; wordpress_logged_in_dedd3d5021a06b0ff73c12d14c2f177c=khatridiwass%7C1760546682%7CZzZ8FgjdB6raupuJWH5eZGeZ75wyprEIiFOa3L9It2E%7C79ea1eb0867a45b7193f34e51f2317ec86e8b0fdb84e236c3c204a9ca45a5ab6; __stripe_mid=2cca6042-5083-44f4-8df0-567693f6898df62026; __stripe_sid=9e97e254-896a-464f-b0a5-fd09a5c1af98d0bd22; sbjs_session=pgs%3D10%7C%7C%7Ccpg%3Dhttps%3A%2F%2Fshop.wiseacrebrew.com%2Faccount%2Fadd-payment-method%2F; _ga_94LZDRFSLM=GS2.1.s1759337024$o1$g1$t1759337231$j16$l0$h0',
    'origin': 'https://shop.wiseacrebrew.com',
    'priority': 'u=1, i',
    'referer': 'https://shop.wiseacrebrew.com/account/add-payment-method/',
    'sec-ch-ua': '"Chromium";v="127", "Not)A;Brand";v="99", "Microsoft Edge Simulate";v="127", "Lemur";v="127"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',
    'x-requested-with': 'XMLHttpRequest',
}

params = {
    'wc-ajax': 'wc_stripe_create_and_confirm_setup_intent',
}

data = {
    'action': 'create_and_confirm_setup_intent',
    'wc-stripe-payment-method': id,
    'wc-stripe-payment-type': 'card',
    '_ajax_nonce': '0700b76ca3',
}

response = requests.post('https://shop.wiseacrebrew.com/', params=params, cookies=cookies, headers=headers, data=data)

print(response.json())