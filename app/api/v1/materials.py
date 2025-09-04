"""Materials API endpoints."""

from flask import jsonify, request

from app.api.v1 import bp
from app.models import Material, Device, DeviceBin


@bp.route('/materials')
def list_materials():
    """List all materials in the dictionary."""
    try:
        # Check if we're in demo mode
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode
            from app.utils.demo_data import get_demo_data, init_demo_data
            
            try:
                demo_data = get_demo_data()
                materials = demo_data.get('materials', {})
                # Initialize demo data if materials are empty
                if not materials:
                    init_demo_data()
                    demo_data = get_demo_data()
                    materials = demo_data.get('materials', {})
            except:
                init_demo_data()
                demo_data = get_demo_data()
                materials = demo_data.get('materials', {})
            
            return jsonify({'ok': True, 'data': materials})
        
        # Production mode with Redis
        materials = Material.list_all()
        material_dict = {m.code: m.to_dict() for m in materials}
        
        return jsonify({'ok': True, 'data': material_dict})
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


@bp.route('/materials', methods=['POST'])
def create_material():
    """Create a new material."""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        if not data.get('code') or not data.get('name'):
            return jsonify({'ok': False, 'error': {'code': 'INVALID_ARGUMENT', 'message': 'Code and name are required'}}), 400
        
        # Check if we're in demo mode
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode
            from app.utils.demo_data import get_demo_data
            demo_data = get_demo_data()
            
            if data['code'] in demo_data['materials']:
                return jsonify({'ok': False, 'error': {'code': 'CONFLICT', 'message': 'Material code already exists'}}), 409
            
            demo_data['materials'][data['code']] = {
                'code': data['code'],
                'name': data['name'],
                'type': data.get('type', 'other'),
                'unit': data.get('unit', 'g'),
                'enabled': True
            }
            
            return jsonify({'ok': True, 'data': {'message': 'Material created successfully'}})
        
        # Production mode
        # Check if material already exists
        existing = Material.get(data['code'])
        if existing:
            return jsonify({'ok': False, 'error': {'code': 'CONFLICT', 'message': 'Material code already exists'}}), 409
        
        material = Material(
            code=data['code'],
            name=data['name'],
            type=data.get('type', 'other'),
            unit=data.get('unit', 'g'),
            enabled=True
        )
        
        if material.save():
            return jsonify({'ok': True, 'data': {'message': 'Material created successfully'}})
        else:
            return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': 'Failed to create material'}}), 500
            
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


@bp.route('/materials/<code>', methods=['PUT'])
def update_material(code):
    """Update a material."""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        # Check if we're in demo mode
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode
            from app.utils.demo_data import get_demo_data
            demo_data = get_demo_data()
            
            if code not in demo_data['materials']:
                return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Material not found'}}), 404
            
            # Update material
            material = demo_data['materials'][code]
            if data.get('name'):
                material['name'] = data['name']
            if data.get('type'):
                material['type'] = data['type']
            if data.get('unit'):
                material['unit'] = data['unit']
            if 'enabled' in data:
                material['enabled'] = data['enabled'] == 'on' or data['enabled'] is True
            
            return jsonify({'ok': True, 'data': {'message': 'Material updated successfully'}})
        
        # Production mode
        material = Material.get(code)
        if not material:
            return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Material not found'}}), 404
        
        # Update fields
        if data.get('name'):
            material.name = data['name']
        if data.get('type'):
            material.type = data['type']
        if data.get('unit'):
            material.unit = data['unit']
        if 'enabled' in data:
            material.enabled = data['enabled'] == 'on' or data['enabled'] is True
        
        if material.save():
            return jsonify({'ok': True, 'data': {'message': 'Material updated successfully'}})
        else:
            return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': 'Failed to update material'}}), 500
            
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


@bp.route('/materials/<code>', methods=['DELETE'])
def delete_material(code):
    """Delete a material."""
    try:
        # Check if we're in demo mode
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode
            from app.utils.demo_data import get_demo_data
            demo_data = get_demo_data()
            
            if code not in demo_data['materials']:
                return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Material not found'}}), 404
            
            del demo_data['materials'][code]
            return jsonify({'ok': True, 'data': {'message': 'Material deleted successfully'}})
        
        # Production mode
        material = Material.get(code)
        if not material:
            return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Material not found'}}), 404
        
        if material.delete():
            return jsonify({'ok': True, 'data': {'message': 'Material deleted successfully'}})
        else:
            return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': 'Failed to delete material'}}), 500
            
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


@bp.route('/devices/<device_id>/bins')
def get_device_bins(device_id):
    """Get bin configuration for a device."""
    try:
        # Check if we're in demo mode
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode
            from app.utils.demo_data import get_demo_data, get_device_bins_demo
            
            try:
                bins = get_device_bins_demo(device_id)
            except:
                bins = []
            
            return jsonify({'ok': True, 'data': bins})
        
        # Production mode
        device = Device.get(device_id)
        if not device:
            return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Device not found'}}), 404
        
        bins = DeviceBin.list_by_device(device_id)
        bin_data = [bin.to_dict() for bin in bins]
        
        return jsonify({'ok': True, 'data': bin_data})
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


@bp.route('/devices/<device_id>/bins', methods=['PUT'])
def update_device_bins(device_id):
    """Update bin configuration for a device."""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        bins_config = data.get('bins', [])
        
        # Check if we're in demo mode
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode
            from app.utils.demo_data import get_demo_data
            demo_data = get_demo_data()
            
            if device_id not in demo_data['devices']:
                return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Device not found'}}), 404
            
            # Update bins configuration
            bins = {}
            for bin_config in bins_config:
                bin_index = bin_config['bin_index']
                bins[bin_index] = {
                    'bin_index': bin_index,
                    'material_code': bin_config.get('material_code', ''),
                    'remaining': bin_config.get('remaining', 0),
                    'capacity': bin_config.get('capacity', 0),
                    'unit': 'g',  # Default unit
                    'threshold_low_pct': bin_config.get('threshold_low_pct', 20),
                    'is_low': False  # Will be calculated
                }
                
                # Calculate if low
                if bins[bin_index]['capacity'] > 0:
                    percentage = (bins[bin_index]['remaining'] / bins[bin_index]['capacity']) * 100
                    bins[bin_index]['is_low'] = percentage < bins[bin_index]['threshold_low_pct']
            
            demo_data['bins'][device_id] = bins
            
            return jsonify({'ok': True, 'data': {'message': 'Bin configuration updated successfully'}})
        
        # Production mode
        device = Device.get(device_id)
        if not device:
            return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Device not found'}}), 404
        
        # Update each bin
        for bin_config in bins_config:
            bin_obj = DeviceBin.get(device_id, bin_config['bin_index'])
            if not bin_obj:
                bin_obj = DeviceBin(
                    device_id=device_id,
                    bin_index=bin_config['bin_index']
                )
            
            bin_obj.material_code = bin_config.get('material_code', '')
            bin_obj.remaining = bin_config.get('remaining', 0)
            bin_obj.capacity = bin_config.get('capacity', 0)
            bin_obj.threshold_low_pct = bin_config.get('threshold_low_pct', 20)
            bin_obj.save()
        
        return jsonify({'ok': True, 'data': {'message': 'Bin configuration updated successfully'}})
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


@bp.route('/devices/<device_id>/sync_materials', methods=['POST'])
def sync_device_materials(device_id):
    """Sync device material status."""
    try:
        # Check if we're in demo mode
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode - just return success
            return jsonify({'ok': True, 'data': {'message': 'Material sync initiated (demo mode)'}})
        
        # Production mode
        device = Device.get(device_id)
        if not device:
            return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Device not found'}}), 404
        
        # In a real implementation, this would send a command to the device
        # to report its current material levels
        from app.models import RemoteCommand
        from app.utils.redis_utils import generate_id, get_current_ts
        
        command = RemoteCommand(
            command_id=generate_id('cmd_'),
            device_id=device_id,
            command_type='sync_materials',
            payload={'request_type': 'material_levels'},
            status='pending',
            issued_ts=get_current_ts()
        )
        
        if command.save():
            return jsonify({'ok': True, 'data': {'message': 'Material sync command queued'}})
        else:
            return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': 'Failed to queue sync command'}}), 500
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500
