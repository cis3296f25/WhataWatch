# WhataWatch
WhataWatch is the solution to movie nights that haven’t had a movie planned. WhataWatch will take an input of the user(s) letterboxd handle and a description of a movie they’d like to watch. It’ll then look at their logged movies and see what kind of movies they enjoy watching and what best matches the kind of movie they would like to watch. It will then suggest a list of potential movies with their descriptions for the user to read.

<img width="316" height="531" alt="Screenshot 2025-10-28 at 11 29 39" src="https://github.com/user-attachments/assets/5d61feb3-0c3a-42bd-97bc-4dbd1f37da58" />


# How to Run

The production version is hosted on **PythonAnywhere**:

👉 **https://whatawatch.pythonanywhere.com/**

1. Open the link above  
2. Click the **Recommender** tab in the top-right  
3. Enter a Letterboxd username (example: "forkbender84" - a working username we have already tested)  
4. Click **Import**  
5. View your personalized recommendations  


# What it does
WhataWatch uses a custom recommendation model built with:
- Letterboxd Data Scraping
- Django Database
- Custom Scoring/Weighting System 
- PythonAnywhere Website

The system:
1. Pulls user’s logged movies from Letterboxd  
2. Builds a preference profile  
3. Compares it to a pre-processed movie dataset  
4. Recommends movies that:
   - match the users liked movies  
   - align with their watch preferences  
   - are not already logged/watched  


# How to contribute
Follow this project board to know the latest status of the project: https://github.com/orgs/cis3296f25/projects/74

### How to build
- Use this github repository: ... 
- Specify what branch to use for a more stable release or for cutting edge development.  
- Specify additional library to download if needed 
- What file and target to compile and run. 
- What is expected to happen when the app start. 
