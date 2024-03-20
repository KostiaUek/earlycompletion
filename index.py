from flask import Flask, render_template, request, redirect, flash, send_file
from flask_socketio import SocketIO
from threading import Thread

from extraction import getSiteBody, checkPage, calculate_metrics, extract_product_ids, checkIfFileExists

import matplotlib.pyplot as plt
import numpy as np
import io
import os
import pandas as pd

app = Flask(__name__)
app.secret_key = ')oD;4mq)9am-%|!$3ezA4rcy5E<Aq.-8eoLL:oa=03!!E|i$va'
socketio = SocketIO(app)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/extraction', methods=['GET', 'POST'])
def extraction():
    if request.method == 'POST':
        print('Extraction here')
        product_id = request.form['product_id'].strip()

        if not product_id:
            flash('Product ID is required.')
            return redirect('/extraction')

        result = checkPage(product_id)

        if not result[0]:
            flash('Product ID is incorrect.')
            return redirect('/extraction')

        check_path = checkIfFileExists(product_id)
        if bool(check_path):
            return redirect(f'/product/{product_id}', code=302)

        return redirect(f'/progress/{product_id}', code=302)
    return render_template('extraction.html')


@app.route('/product/<product_id>')
def product(product_id):
    reviews = getSiteBody(product_id, socketio)
    return render_template('product_page.html', reviews=reviews, product_id=product_id)


@app.route('/progress/<product_id>')
def progress(product_id):
    Thread(target=getSiteBody, args=(product_id, socketio)).start()
    return render_template('progress_page.html', product_id=product_id)


@app.route('/list')
def product_list_page():
    product_ids = extract_product_ids()
    products = []
    for product_id in product_ids:
        metrics = calculate_metrics(product_id)
        if metrics:
            products.append({
                'id': product_id,
                'name': f'Product {product_id}', 
                **metrics
            })

    return render_template('product_list_page.html', products=products)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/charts/<product_id>')
def product_charts(product_id):
    reviews_data = getSiteBody(product_id, socketio)
    scores = [float(review['score'].split('/')[0].replace(",", ".")) for review in reviews_data]
    recommendations = [1 if review['author_recommendation'] == '\nPolecam\n' else 0 for review in reviews_data]

    fig, ax = plt.subplots()
    ax.pie([sum(recommendations), len(recommendations) - sum(recommendations)],
           labels=['Recommended', 'Not Recommended'], autopct='%1.1f%%')
    plt.title('Recommendation Share')
    pie_chart_image = io.BytesIO()
    plt.savefig(pie_chart_image, format='png')
    pie_chart_image.seek(0)

    pie_chart_file = 'pie_chart.png'
    plt.savefig("./static/" + pie_chart_file)

    plt.figure()
    plt.bar(np.unique(scores), [scores.count(score) for score in np.unique(scores)])
    plt.title('Number of Opinions by Star Rating')
    plt.xlabel('Star Rating')
    plt.ylabel('Number of Opinions')
    bar_chart_image = io.BytesIO()
    plt.savefig(bar_chart_image, format='png')
    bar_chart_image.seek(0)

    bar_chart_file = 'bar_chart.png'
    plt.savefig("./static/" + bar_chart_file)

    return render_template('product_charts.html', pie_chart_image=pie_chart_image, bar_chart_image=bar_chart_image,
                           product_id=product_id)


@app.route('/download_opinions/<product_id>/<format>')
def download_opinions(product_id, format):
    file_path = f'reviewed_products/{product_id}.json'
    if not os.path.exists(file_path):
        return "File not found", 404

    df = pd.read_json(file_path)

    if format == 'csv':
        df.to_csv('opinions.csv', index=False)
        return send_file('opinions.csv', as_attachment=True)
    elif format == 'xlsx':
        df.to_excel('opinions.xlsx', index=False)
        return send_file('opinions.xlsx', as_attachment=True)
    elif format == 'json':
        df.to_json('opinions.json', orient='records')
        return send_file('opinions.json', as_attachment=True)
    else:
        return "Invalid format", 400


if __name__ == "__main__":
    socketio.run(app=app, debug=True, allow_unsafe_werkzeug=True)
