def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]  # In case there are multiple addresses, take the first one
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_host(request):
    return request.META.get('HTTP_HOST')