import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from datetime import datetime
import altair as alt

@st.cache

def parse_date(date_string):
    try:
        return datetime.strptime(date_string, '%B %d, %Y')
    except ValueError:
        return datetime.strptime(date_string, '%b %d, %Y')

def parse_date2(date_string):
    return datetime.strptime(date_string, '%d %b %Y')

def load_data():
    """ Loads in 4 dataframes and does light feature engineering"""
    df_agg = pd.read_csv('Aggregated_Metrics_By_Video.csv').iloc[1:,:]
    df_agg.columns = ['Video','Video title','Video publish time','Comments added','Shares','Dislikes','Likes',
                      'Subscribers lost','Subscribers gained','RPM(USD)','CPM(USD)','Average % viewed','Average view duration',
                      'Views','Watch time (hours)','Subscribers','Your estimated revenue (USD)','Impressions','Impressions ctr(%)']
    df_agg['Video publish time'] = df_agg['Video publish time'].apply(parse_date)
    df_agg['Average view duration'] = df_agg['Average view duration'].apply(lambda x: datetime.strptime(x,'%H:%M:%S'))
    df_agg['Avg_duration_sec'] = df_agg['Average view duration'].apply(lambda x: x.second + x.minute*60 + x.hour*3600)
    df_agg['Engagement_ratio'] =  (df_agg['Comments added'] + df_agg['Shares'] +df_agg['Dislikes'] + df_agg['Likes']) /df_agg.Views
    df_agg['Views / sub gained'] = df_agg['Views'] / df_agg['Subscribers gained']
    df_agg.sort_values('Video publish time', ascending = False, inplace = True)    
    df_agg_sub = pd.read_csv('Aggregated_Metrics_By_Country_And_Subscriber_Status.csv')
    df_comments = pd.read_csv('Aggregated_Metrics_By_Video.csv')
    df_time = pd.read_csv('Video_Performance_Over_Time.csv')
    df_time['Date']=df_time['Date'].str.replace('Sept','Sep').apply(parse_date2)
    return df_agg, df_agg_sub, df_comments, df_time 


#create dataframes from the function 
df_agg, df_agg_sub, df_comments, df_time = load_data()

#additional data engineering for aggregated data 
df_agg_diff = df_agg.copy()
metric_date_12mo = df_agg_diff['Video publish time'].max() - pd.DateOffset(months =12)
numeric_cols = df_agg_diff.select_dtypes(include=['number']).columns
median_agg = df_agg_diff[df_agg_diff['Video publish time']>=metric_date_12mo][numeric_cols].median()


#create differences from the median for values 
#Just numeric columns 
numeric_cols = np.array((df_agg_diff.dtypes == 'float64') | (df_agg_diff.dtypes == 'int64'))
df_agg_diff.iloc[:,numeric_cols] = (df_agg_diff.iloc[:,numeric_cols] - median_agg).div(median_agg)


#merge daily data with publish data to get delta 
df_time_diff = pd.merge(df_time, df_agg.loc[:,['Video','Video publish time']], left_on ='External Video ID', right_on = 'Video')
df_time_diff['days_published'] = (df_time_diff['Date'] - df_time_diff['Video publish time']).dt.days

# get last 12 months of data rather than all data 
date_12mo = df_agg['Video publish time'].max() - pd.DateOffset(months =12)
df_time_diff_yr = df_time_diff[df_time_diff['Video publish time'] >= date_12mo]

# get daily view data (first 30), median & percentiles 
views_days = pd.pivot_table(df_time_diff_yr,index= 'days_published',values ='Views', aggfunc = [np.mean,np.median,lambda x: np.percentile(x, 80),lambda x: np.percentile(x, 20)]).reset_index()
views_days.columns = ['days_published','mean_views','median_views','80pct_views','20pct_views']
views_days = views_days[views_days['days_published'].between(0,30)]
views_cumulative = views_days.loc[:,['days_published','median_views','80pct_views','20pct_views']] 
views_cumulative.loc[:,['median_views','80pct_views','20pct_views']] = views_cumulative.loc[:,['median_views','80pct_views','20pct_views']].cumsum()



###############################################################################
#Start building Streamlit App
###############################################################################

add_sidebar = st.sidebar.selectbox('Aggregate or Individual Video', ('Aggregate Metrics','Individual Video Analysis','test'))

#Show individual metrics 
if add_sidebar == 'Aggregate Metrics':
    st.write("YouTube Aggregated Data")
    df_agg_metrics = df_agg[['Video publish time','Views','Likes','Subscribers','Shares','Comments added','RPM(USD)','Average % viewed',
                             'Avg_duration_sec', 'Engagement_ratio','Views / sub gained']]
    metric_date_6mo = df_agg_metrics['Video publish time'].max() - pd.DateOffset(months =6)
    metric_date_12mo = df_agg_metrics['Video publish time'].max() - pd.DateOffset(months =12)
    numeric_cols = df_agg_metrics.select_dtypes(include=['number']).columns
    metric_medians6mo = df_agg_metrics[df_agg_metrics['Video publish time'] >= metric_date_6mo][numeric_cols].median()
    metric_medians12mo = df_agg_metrics[df_agg_metrics['Video publish time'] >= metric_date_12mo][numeric_cols].median()

    col1, col2, col3, col4, col5 = st.columns(5)
    columns = [col1, col2, col3, col4, col5]

    count = 0
    for i in metric_medians6mo.index:
        with columns[count]:
            delta = (metric_medians6mo[i] - metric_medians12mo[i])/metric_medians12mo[i]
            st.metric(label= i, value = round(metric_medians6mo[i],1), delta = "{:.2%}".format(delta))
            count += 1
            if count >= 5:
                count = 0

    #get date information / trim to relevant data 
    df_agg_diff['Publish_date'] = df_agg_diff['Video publish time'].apply(lambda x: x.date())
    df_agg_diff_final = df_agg_diff.loc[:,['Video title','Publish_date','Views','Likes','Subscribers','Shares','Comments added','RPM(USD)','Average % viewed',
                             'Avg_duration_sec', 'Engagement_ratio','Views / sub gained']]
    
    # Selecting numeric columns explicitly
    numeric_cols = df_agg_diff_final.select_dtypes(include=['number']).columns

    # Calculating median for selected numeric columns
    median_values = df_agg_diff_final[numeric_cols].median()

    # Converting median values to percentages
    df_to_pct = {}
    for col, median_value in median_values.items():
        df_to_pct[col] = '{:.1%}'.format(median_value)
    
    st.dataframe(df_agg_diff_final)

if add_sidebar == 'Individual Video Analysis':
    videos = tuple(df_agg['Video title'])
    st.write("Individual Video Performance")
    video_select = st.selectbox('Pick a Video:', videos)
    
    agg_filtered = df_agg[df_agg['Video title'] == video_select]
    agg_sub_filtered = df_agg_sub[df_agg_sub['Video Title'] == video_select]
    #agg_sub_filtered['Country'] = agg_sub_filtered['Country Code'].apply(audience_simple)
    agg_sub_filtered.sort_values('Is Subscribed', inplace= True)   
    
    fig = px.bar(agg_sub_filtered, x ='Views', y='Is Subscribed', orientation ='h')
    #order axis 
    st.plotly_chart(fig)

    agg_time_filtered = df_time_diff[df_time_diff['Video Title'] == video_select]
    first_30 = agg_time_filtered[agg_time_filtered['days_published'].between(0,30)]
    first_30 = first_30.sort_values('days_published')
    
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=views_cumulative['days_published'], y=views_cumulative['20pct_views'],
                    mode='lines',
                    name='20th percentile', line=dict(color='purple', dash ='dash')))
    fig2.add_trace(go.Scatter(x=views_cumulative['days_published'], y=views_cumulative['median_views'],
                        mode='lines',
                        name='50th percentile', line=dict(color='black', dash ='dash')))
    fig2.add_trace(go.Scatter(x=views_cumulative['days_published'], y=views_cumulative['80pct_views'],
                        mode='lines', 
                        name='80th percentile', line=dict(color='royalblue', dash ='dash')))
    fig2.add_trace(go.Scatter(x=first_30['days_published'], y=first_30['Views'].cumsum(),
                        mode='lines', 
                        name='Current Video' ,line=dict(color='firebrick',width=8)))
        
    fig2.update_layout(title='View comparison first 30 days',
                   xaxis_title='Days Since Published',
                   yaxis_title='Cumulative views')
    st.plotly_chart(fig2)

if add_sidebar == 'test':
    st.header('st.write')
    
    # Example 1
    
    st.write('Hello, *World!* :sunglasses:')
    
    # Example 2
    
    st.write(1234)
    
    # Example 3
    
    df = pd.DataFrame({
         'first column': [1, 2, 3, 4],
         'second column': [10, 20, 30, 40]
         })
    st.write(df)
    
    # Example 4
    
    st.write('Below is a DataFrame:', df, 'Above is a dataframe.')
    
    # Example 5
    
    df2 = pd.DataFrame(
         np.random.randn(200, 3),
         columns=['a', 'b', 'c'])
    c = alt.Chart(df2).mark_circle().encode(
         x='a', y='b', size='c', color='c', tooltip=['a', 'b', 'c'])
    st.write(c)
        
    #Sliders
    st.header('st.slider')

    # Example 1
    
    st.subheader('Slider')
    
    age = st.slider('How old are you?', 0, 130, 25)
    st.write("I'm ", age, 'years old')
    
    # Example 2
    
    st.subheader('Range slider')
    
    values = st.slider(
         'Select a range of values',
         0.0, 100.0, (25.0, 75.0))
    st.write('Values:', values)
       
    # Example 4
    
    st.subheader('Datetime slider')
    
    start_time = st.slider(
         "When do you start?",
         value=datetime(2020, 1, 1, 9, 30),
         format="MM/DD/YY - hh:mm")
    st.write("Start time:", start_time)

    #linecharts

    st.header('Line chart')

    chart_data = pd.DataFrame(
         np.random.randn(20, 3),
         columns=['a', 'b', 'c'])
    
    st.line_chart(chart_data)

    st.header('st.selectbox')
    
    option = st.selectbox(
         'What is your favorite color?',
         ('Blue', 'Red', 'Green'))
    
    st.write('Your favorite color is ', option)
    
    st.header('st.multiselect')
    
    options = st.multiselect(
         'What are your favorite colors',
         ['Green', 'Yellow', 'Red', 'Blue'],
         ['Yellow', 'Red'])
    
    st.write('You selected:', options)
    
    st.header('st.checkbox')
    
    st.write ('What would you like to order?')
    
    icecream = st.checkbox('Ice cream')
    coffee = st.checkbox('Coffee')
    cola = st.checkbox('Cola')
    
    if icecream:
         st.write("Great! Here's some more 🍦")
    
    if coffee: 
         st.write("Okay, here's some coffee ☕")
    
    if cola:
         st.write("Here you go 🥤")
    st.header('st.latex')
    
    st.latex(r'''
         a + ar + a r^2 + a r^3 + \cdots + a r^{n-1} =
         \sum_{k=0}^{n-1} ar^k =
         a \left(\frac{1-r^{n}}{1-r}\right)
         ''')
