from flask import Flask, request, jsonify
from abrasio import Abrasio
from abrasio.http import StealthClientSync
from abrasio.utils.human import human_click, human_type, human_scroll
import base64

app = Flask(__name__)

# ---------------------------------------------------------------
# /browser endpoint
# ---------------------------------------------------------------

ACTION_MAP = {}

def register_action(name):
    def decorator(fn):
        ACTION_MAP[name] = fn
        return fn
    return decorator

@register_action('click')
async def _(page, args): return await page.locator(args[0]).click()

@register_action('human_click')
async def _(page, args): return await human_click(page, args[0])

@register_action('fill')
async def _(page, args): return await page.locator(args[0]).fill(args[1])

@register_action('wait_for_timeout')
async def _(page, args): return await page.wait_for_timeout(args[0])

@register_action('wait_for_selector')
async def _(page, args):
    timeout = args[1] if len(args) > 1 else 30000
    return await page.wait_for_selector(args[0], timeout=timeout)

@register_action('wait_for')
async def _(page, args):
    timeout = args[1] if len(args) > 1 else 30000
    state = args[2] if len(args) > 2 else 'visible'
    return await page.locator(args[0]).wait_for(timeout=timeout, state=state)

@register_action('goto')
async def _(page, args): return await page.goto(args[0])

@register_action('press')
async def _(page, args): return await page.locator(args[0]).press(args[1])

@register_action('hover')
async def _(page, args): return await page.locator(args[0]).hover()

@register_action('select_option')
async def _(page, args): return await page.locator(args[0]).select_option(args[1])

@register_action('check')
async def _(page, args): return await page.locator(args[0]).check()

@register_action('uncheck')
async def _(page, args): return await page.locator(args[0]).uncheck()

@register_action('evaluate')
async def _(page, args): return await page.evaluate(args[0])

@register_action('type')
async def _(page, args): return await page.locator(args[0]).type(args[1])

@register_action('human_type')
async def _(page, args): return await human_type(page, args[1], args[0])

@register_action('scroll')
async def _(page, args):
    x, y = (args[0], args[1]) if len(args) >= 2 else (0, args[0])
    return await page.evaluate(f'window.scrollTo({x}, {y})')

@register_action('human_scroll')
async def _(page, args): return await human_scroll(page, args[0], args[1])

@register_action('screenshot')
async def _(page, args):
    path = args[0] if args else "screenshot.png"
    path = path.replace("..", "")
    return await page.screenshot(path=path)

RESPONSE_MAP = {
    'content':    lambda p: p.content(),
    'title':      lambda p: p.title(),
    'url':        lambda p: p.url,
    'cookies':    lambda p: p.context.cookies(),
    'screenshot': lambda p: base64.b64encode(p.screenshot()).decode('utf-8'),
}

@app.route('/browser', methods=['POST'])
async def browser():
    body = request.get_json()

    url = body.get('url')
    if not url:
        return jsonify({'error': '"url" is required'}), 400

    async with Abrasio(headless=False) as browser:
        page = await browser.new_page()

        try:
            await page.goto(url)

            for act in body.get('actions', []):
                name = act.get('instruction')
                handler = ACTION_MAP.get(name)
                if not handler:
                    return jsonify({'error': f'Unknown instruction: {name}'}), 400
                await handler(page, act.get('arguments', []))

            response_type = body.get('response', 'content')
            handler = RESPONSE_MAP.get(response_type)
            if handler:
                result = await handler(page)
            else:
                attr = getattr(page, response_type, None)
                if attr is None:
                    return jsonify({'error': f'Unknown response type: {response_type}'}), 400
                result = attr() if callable(attr) else attr

            return jsonify({'result': result})
        except Exception as e:
            print(e)
            return jsonify({'error': str(e)}), 500

# ---------------------------------------------------------------
# /curl endpoint
# ---------------------------------------------------------------

@app.route('/curl', methods=['POST'])
def curl():
    body = request.get_json()

    url = body.get('url')
    if not url:
        return jsonify({'error': '"url" is required'}), 400

    config = body.get('config', {})

    with StealthClientSync(timeout=config.get('timeout', 30), verify=config.get('verify', True)) as client:
        req = client.request(
            method=body.get('method', 'GET'),
            url=url,
            headers=body.get('headers', {}),
            cookies=body.get('cookies', {}),
            data=body.get('data', None),
            json=body.get('json', None),
            allow_redirects=config.get('allow_redirects', True),
        )
        return jsonify({
            'status': req.status_code,
            'headers': req.headers,
            'content': req.text,
        })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8193)
