from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello! AI客服测试成功！"

if __name__ == '__main__':
    print("测试服务器启动...")
    print("访问: http://localhost:5000")
    app.run(debug=True, port=5000)
