#
#

import uuid
import time
import sqlite3
from flask import Flask, request, abort, g, json

from flask_app import app, BASEPATH, db, auth_required, AUTHLVL

# the app instance is created in __init__

# device generates a random code and posts it to the server
# server waits for user to confirm it
@app.route( BASEPATH+'/link/<in_code>', methods=['GET'] )
def test_device_token( in_code ):
	# returns true/false if someone has claimed the device-code
	# TODO: check that originating IP-addr is same?
	# TODO: send device-token to the device so it can auth next time
	rtn = { 'info':'unknown error', 'status':'error' }
	#rtn['token'] = uuid-token from claim_device_code
	try:
		dbc = db.get_db()
		userid = ''
		time_created = 0
		time_now = int(time.time())
		app.logger.warning( 'looking for devcode='+in_code )
		for row in dbc.execute( 'select * from DevcodeDB where devcode=?', [in_code] ):
			userid = row['userid']
			time_created = row['time_create']
		app.logger.warning( 'found userid='+userid )
		#app.logger.info( 'time='+str(time_now)+'-'+str(time_created)+'='+str(time_now-time_created)+'::'+str(app.config['DEVCODE_TIMEOUT']))
		if( userid == '' ):
			rtn['info'] = 'cannot find device-code'
			rtn['status'] = 'error'
		elif( userid == '_null' ):
			rtn['info'] = 'device-code is not claimed'
			rtn['status'] = 'retry'
		elif( (time_now-time_created) > app.config['DEVCODE_TIMEOUT'] ):
			rtn['info'] = 'device-code has expired'
			rtn['status'] = 'error'
		else:
			new_token = uuid.uuid1().hex
			time_now = int(time.time())
			app.logger.warning( 'creating new token='+new_token )
			dbc.execute( 'insert into TokenDB (token,userid,time_create,device_name) values (?,?,?,?)', [new_token,userid,time_now,'default'])
			dbc.execute( 'delete from DevcodeDB where devcode=?', [in_code] )
			dbc.commit()
			rtn['info'] = 'devcode was claimed by a user'
			rtn['token'] = new_token
			rtn['status'] = 'ok'
	except sqlite3.Error as e:
		app.logger.warning( 'db-error: '+str(e) )
		rtn['info'] = 'error in database query'
		rtn['status'] = 'error'
	return json.jsonify(rtn)

@app.route( BASEPATH+'/link/', methods=['POST'] )
def reg_device_code():
	rtn = { 'info':'code was not registered', 'status':'error' }
	if( 'authcode' in request.form ):
		# TODO: store originaing IP-addr in database too?
		authcode = request.form['authcode']
		time_now = int(time.time())
		app.logger.warning( 'registering dev-code='+authcode )
		# TODO: check for device-code already in db
		try:
			dbc = db.get_db()
			dbc.execute( 'insert into DevcodeDB (devcode,claimed,userid,time_create) values (?,?,?,?) ', [authcode,'N','_null',time_now] )
			dbc.commit()
			rtn['info'] = 'code was registered'
			rtn['status'] = 'ok'
		except sqlite3.Error as e:
			app.logger.warning( 'db-error: '+str(e) )
			rtn['info'] = 'database error'
	return json.jsonify(rtn)

@app.route( BASEPATH+'/activate/<in_code>', methods=['GET'] )
@auth_required( AUTHLVL.USER )
def claim_device_code( in_code ):
	# a user is claiming a device-code
	# TODO: allow user to name the device that will be attached to this device-key
	rtn = { 'info':'could not find device-code', 'status':'error' }
	try:
		dbc = db.get_db()
		flag = False
		for row in dbc.execute( 'select * from DevcodeDB where devcode=?', [in_code] ):
			flag = True
		if( flag ):
			dbc.execute( 'update DevcodeDB set claimed=?, userid=? where devcode=?', ['Y',g.auth_userid,in_code] )
			dbc.commit()
			rtn['info'] = 'device-code was claimed'
			rtn['status'] = 'ok'
	except sqlite3.Error as e:
		app.logger.warning( 'db-error: '+str(e) )
		rtn['info'] = 'database error'
	return json.jsonify(rtn)

@app.route( BASEPATH+'/data/<in_event>', methods=['POST'] )
@auth_required( AUTHLVL.DEVICE )
def push_data( in_event ):
	rtn = { 'info':'event name not recognized', 'status':'error' }
	if( in_event in app.config['EVENT_LIST'] ):
		#authuser = request.authorization['username']
		authuser = g.token_userid
		app.logger.info( 'data-push '+in_event+' on behalf of userid='+authuser )
		# TODO: this changes rtn from hash to list!
		rtn = []
		try:
			dbc = db.get_db()
			for row in dbc.execute( 'select * from SubsDB where event=? and userid=?', [in_event,authuser] ):
				rtn.append( { 'subid':row['subid'], 'userid':row['userid'], 'target_url':row['target_url'] } )
		except:
			rtn['info'] = 'database error'
	return json.jsonify(rtn)