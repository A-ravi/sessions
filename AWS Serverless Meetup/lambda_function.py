import json
from datetime import datetime
import boto3
import botocore.exceptions

dynamodb = boto3.client('dynamodb')

beverage_list = {
    "Espresso": 2.25,
    "Americano": 2.35,
    "Flat White":3.25,
    "Doppio": 4.50,
    "Macchiato": 3.10,
    "Cappuccino": 5.23,
    "Mocha": 7.01,
    "Affogato": 8.15,
    "Irish Coffee": 7.57,
    "Iced Coffee": 5.39
    }
    
beverage_ingredents = {
    "Espresso":[{"itemcode": "ES","quantity": 1}],
    "Americano":[{"itemcode": "ES","quantity": 1}, {"itemcode": "WR","quantity": 1}],
    "Flat White":[{"itemcode": "ES","quantity": 1}, {"itemcode": "MK","quantity": 2}],
    "Doppio":[{"itemcode": "ES","quantity": 2}],
    "Macchiato":[{"itemcode": "ES","quantity": 1}, {"itemcode": "MK","quantity": 1}, {"itemcode": "FM","quantity": 1}],
    "Cappuccino":[{"itemcode": "ES","quantity": 1}, {"itemcode": "MK","quantity": 1}, {"itemcode": "FM","quantity": 2},{"itemcode": "CP","quantity": 1}],
    "Mocha":[{"itemcode": "ES","quantity": 1}, {"itemcode": "MK","quantity": 1}, {"itemcode": "FM","quantity": 2},{"itemcode": "CP","quantity": 2}],
    "Affogato":[{"itemcode": "ES","quantity": 2}, {"itemcode": "VI","quantity": 1}],
    "Irish Coffee":[{"itemcode": "ES","quantity": 1}, {"itemcode": "WY","quantity": 1}, {"itemcode": "SR","quantity": 1},{"itemcode": "FM","quantity": 1}],
    "Iced Coffee":[{"itemcode": "ES","quantity": 1}, {"itemcode": "IC","quantity": 2}, {"itemcode": "MK","quantity": 2},{"itemcode": "SR","quantity": 2}],
    }


itemcode = {
    "WR": 0.10,
    "IC": 0.32,
    "MK": 0.50,
    "FM": 0.35,
    "SR": 0.75,
    "ES": 2.25,
    "CP": 1.78,
    "VI": 3.65,
    "WY": 4.22,
}

response_header={'Access-Control-Allow-Headers': 'Content-Type','Access-Control-Allow-Origin': '*','Access-Control-Allow-Methods': 'OPTIONS,POST,GET'}

def lambda_handler(event, context):
    dynamodb = boto3.client('dynamodb')
    s3 = boto3.client("s3")
    
    # if get Request response that  we acceept request from UI only
    if event["httpMethod"] == "GET":
        # return the message
        return {
            'statusCode': 200,
            'body': "Use the UI only to order for coffee",
            'headers': response_header
        }
    # If requset if post then process the order
    elif event["httpMethod"] == "POST":
        # print(event)
        order_request = json.loads(event['body'])
        # print(order_request)
        order_status = "rejected"
        order_item = order_request['order']
        # print(order_item)
        
        if order_item in beverage_list or order_item == "custom":
            order_status = "accepted"
            
        # push the data into the database
        # 1 .generate the orderid, timestamp in python
        now = datetime.now()
        formattedtime = now.strftime("%Y-%m-%d-%H%M%S")
        orderid = "order-"+formattedtime
        order_cost = calculate_order_price(order_request)
    
        # put data in the orders tables
        if order_item in beverage_list:
            response = dynamodb.put_item(
                                        Item={
                                            'orderid': {
                                                'S': orderid,
                                            },
                                            'timestamp': {
                                                'S': str(now),
                                            },
                                            'item': {
                                                'S': order_item,
                                            },
                                            'cost': {
                                                'N': str(order_cost),
                                            },
                                        },
                                        TableName='coffeshop-orders',
                                    )
                                
            # update the stock table
            # for each ingredents 
            #   check if the item exist and get the values
            #   then update the value
            for items in beverage_ingredents[order_item]:
                item = items["itemcode"]
                qty = items["quantity"]
                
                response = dynamodb.get_item(TableName="coffeeshop-stocks", Key={'item': {'S':item}})
                
                if "Item" in response:
                    response = dynamodb.update_item(
                                         Key={"item": {"S": item}},
                                         UpdateExpression="set consumedqty = consumedqty + :n",
                                         ExpressionAttributeValues={
                                             ":n": {"N": str(qty)},
                                         },
                                         ReturnValues="UPDATED_NEW",
                                         TableName="coffeeshop-stocks")
                else:
                    response = dynamodb.put_item(
                                        Item={
                                            'item': {
                                                'S': item,
                                            },
                                            'consumedqty': {
                                                'N': str(qty),
                                            },
                                        },
                                        TableName='coffeeshop-stocks',
                                    )
            
        if order_item == "custom":
            response = dynamodb.put_item(
                                        Item={
                                            'orderid': {
                                                'S': orderid,
                                            },
                                            'ingredients': {
                                                'S': json.dumps(order_request['ingredients']),
                                            }
                                        },
                                        TableName='coffeshop-diy',
                                    )                
            for items in order_request['ingredients']:
                item = items["itemcode"]
                qty = items["quantity"]
                
                response = dynamodb.get_item(TableName="coffeeshop-stocks", Key={'item': {'S':item}})
                
                if "Item" in response:
                    response = dynamodb.update_item(
                                         Key={"item": {"S": item}},
                                         UpdateExpression="set consumedqty = consumedqty + :n",
                                         ExpressionAttributeValues={
                                             ":n": {"N": str(qty)},
                                         },
                                         ReturnValues="UPDATED_NEW",
                                         TableName="coffeeshop-stocks")
                else:
                    response = dynamodb.put_item(
                                        Item={
                                            'item': {
                                                'S': item,
                                            },
                                            'consumedqty': {
                                                'N': str(qty),
                                            },
                                        },
                                        TableName='coffeeshop-stocks',
                                    )

        
        # upload the file in the bucket
        filecontent = order_item+', '+str(order_cost)
        keyname = 'order_notes/'+orderid+'.txt'
        response = s3.put_object(Body=str.encode(filecontent),Bucket="coffeeshopbucket",Key=keyname)
        
        
        # return statement
        return {
        'statusCode': 200,
        'body': json.dumps({
            'response': order_status,
            'item': order_item,
            'cost': order_cost
            }),

        'headers': response_header
    }

def calculate_order_price(body):
    if body['order'] in beverage_list:
        # print( beverage_list[body['order']] + 2.25)
        return beverage_list[body['order']] + 2.25
    elif body['order'] == "custom":
        total = 0.0
        # print(body)
        for items in body['ingredients']:
            print("this is the body of ingredients ->", items)
            item = items["itemcode"]
            qty = items["quantity"]
            # print("this is item in items -> ",item)
            # print("code and qty ->", item, qty)
            total += float(itemcode[item]) * float(qty)
        # print(total + 2.25)
        return total + 2.25
