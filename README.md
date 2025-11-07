# WhataWatch
WhataWatch is the solution to movie nights that haven’t had a movie planned. WhataWatch will take an input of the user(s) letterboxd handle and a description of a movie they’d like to watch. It’ll then look at their logged movies and see what kind of movies they enjoy watching and what best matches the kind of movie they would like to watch. It will then suggest a list of potential movies with their descriptions for the user to read.

<img width="316" height="531" alt="Screenshot 2025-10-28 at 11 29 39" src="https://github.com/user-attachments/assets/5d61feb3-0c3a-42bd-97bc-4dbd1f37da58" />


# How to run
Make sure you have python installed and run these in your terminal to download the libraries used in the program.
```
pip install -r requirements.txt
pip install matplotlib numpy pillow
```
if you are on a Mac you may need to add a 3 after pip (pip3)

```
python ./GitHub/WhataWatch/letterboxdpy/diary.py --user [username] --open-poster
```

a csv file will be made in ./WhataWatch/letterboxdpy/output_csv

and the program will show your most recent watch



# How to contribute
Follow this project board to know the latest status of the project: https://github.com/orgs/cis3296f25/projects/74

### How to build
- Use this github repository: ... 
- Specify what branch to use for a more stable release or for cutting edge development.  
- Specify additional library to download if needed 
- What file and target to compile and run. 
- What is expected to happen when the app start. 
