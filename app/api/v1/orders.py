"""Orders API endpoints."""

from flask import jsonify, request
from datetime import datetime, date, timedelta

from app.api.v1 import bp
from app.models import Device, Order
from app.utils.redis_utils import get_current_ts


@bp.route('/orders')
def list_orders():
    """List orders with filtering and pagination."""
    try:
        # Check if we're in demo mode (Redis not available)
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode
            from app.utils.demo_data import get_orders_list, init_demo_data
            
            try:
                orders = get_orders_list(request.args)
            except:
                init_demo_data()
                orders = get_orders_list(request.args)
            
            # Calculate statistics
            statistics = calculate_order_statistics(orders['orders'])
            
            return jsonify({
                'ok': True,
                'data': {
                    'orders': orders['orders'],
                    'pagination': orders['pagination'],
                    'statistics': statistics
                }
            })
        
        # Production mode with Redis (original implementation)
        # Query parameters
        device_id = request.args.get('device_id')
        merchant_id = request.args.get('merchant_id')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        payment_status = request.args.get('payment_status')
        order_status = request.args.get('order_status')
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 50)), 100)
        
        orders = []
        total_count = 0
        
        if device_id:
            # Get orders for specific device
            device = Device.get(device_id)
            if device:
                device_orders = Order.list_by_device(device_id, 
                                                   from_date=from_date, 
                                                   to_date=to_date,
                                                   limit=page_size * 2)
                orders.extend(device_orders)
        else:
            # Get orders across all devices (simplified)
            devices = Device.list_recently_seen(limit=100)
            for device in devices:
                device_orders = Order.list_by_device(device.device_id,
                                                   from_date=from_date,
                                                   to_date=to_date,
                                                   limit=20)
                orders.extend(device_orders)
        
        # Apply additional filters
        if payment_status:
            orders = [o for o in orders if o.payment_status == payment_status]
        
        if order_status:
            orders = [o for o in orders if o.order_status == order_status]
        
        # Sort by timestamp (most recent first)
        orders.sort(key=lambda x: x.created_ts or 0, reverse=True)
        
        # Pagination
        total_count = len(orders)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_orders = orders[start_idx:end_idx]
        
        # Convert to dict format
        order_data = [order.to_dict() for order in page_orders]
        
        # Calculate statistics
        statistics = calculate_order_statistics(order_data)
        
        return jsonify({
            'ok': True,
            'data': {
                'orders': order_data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total_count,
                    'has_more': end_idx < total_count
                },
                'statistics': statistics
            }
        })
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


@bp.route('/orders/<order_id>')
def get_order(order_id):
    """Get order details."""
    try:
        # Check if we're in demo mode
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode
            from app.utils.demo_data import get_demo_data
            demo_data = get_demo_data()
            order_data = demo_data['orders'].get(order_id)
            
            if not order_data:
                return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Order not found'}}), 404
            
            return jsonify({'ok': True, 'data': order_data})
        
        # Production mode
        order = Order.get(order_id)
        if not order:
            return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Order not found'}}), 404
        
        return jsonify({'ok': True, 'data': order.to_dict()})
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


@bp.route('/orders/<order_id>/refund', methods=['POST'])
def refund_order(order_id):
    """Refund an order."""
    try:
        # Check if we're in demo mode
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode
            from app.utils.demo_data import get_demo_data
            demo_data = get_demo_data()
            order_data = demo_data['orders'].get(order_id)
            
            if not order_data:
                return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Order not found'}}), 404
            
            # Update order status in demo data
            order_data['payment_status'] = 'refunded'
            order_data['order_status'] = 'cancelled'
            
            return jsonify({'ok': True, 'data': {'message': 'Order refunded successfully'}})
        
        # Production mode
        order = Order.get(order_id)
        if not order:
            return jsonify({'ok': False, 'error': {'code': 'NOT_FOUND', 'message': 'Order not found'}}), 404
        
        if order.payment_status != 'paid':
            return jsonify({'ok': False, 'error': {'code': 'INVALID_STATE', 'message': 'Order cannot be refunded'}}), 400
        
        # Update order status
        order.payment_status = 'refunded'
        order.order_status = 'cancelled'
        order.updated_ts = get_current_ts()
        order.save()
        
        return jsonify({'ok': True, 'data': {'message': 'Order refunded successfully'}})
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


@bp.route('/orders/export')
def export_orders():
    """Export orders to CSV."""
    try:
        # This would typically generate and return a CSV file
        # For now, return a simple message
        return jsonify({'ok': True, 'data': {'message': 'Export functionality not yet implemented'}})
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


@bp.route('/orders/<order_id>/receipt')
def get_order_receipt(order_id):
    """Get order receipt (PDF)."""
    try:
        # This would typically generate and return a PDF receipt
        # For now, return a simple message
        return jsonify({'ok': True, 'data': {'message': 'Receipt generation not yet implemented'}})
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


def calculate_order_statistics(orders):
    """Calculate order statistics."""
    if not orders:
        return {
            'total_orders': 0,
            'total_revenue_cents': 0,
            'avg_order_value_cents': 0,
            'success_rate': 0
        }
    
    total_orders = len(orders)
    completed_orders = [o for o in orders if o.get('order_status') == 'completed']
    total_revenue = sum(o.get('total_amount_cents', 0) for o in completed_orders)
    success_rate = len(completed_orders) / total_orders * 100 if total_orders > 0 else 0
    avg_order_value = total_revenue / len(completed_orders) if completed_orders else 0
    
    return {
        'total_orders': total_orders,
        'total_revenue_cents': total_revenue,
        'avg_order_value_cents': int(avg_order_value),
        'success_rate': round(success_rate, 1)
    }
