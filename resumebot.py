import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
import re
import pandas as pd

# --- Streamlit Setup ---
st.set_page_config(page_title="InterviewBot 🤖", page_icon="🧠", layout="centered")
st.markdown("""
    <style>
    .reportview-container {
        background-color: #f7f9fc;
        padding: 1.5rem;
    }
    .stTextArea textarea {
        background-color: #fff;
        font-size: 16px;
    }
    .stButton>button {
        font-size: 16px;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 AI InterviewBot")
st.markdown("🚀 10-question AI-powered interview. Get evaluated & scored based on your **resume** and **role**.")

# --- Session State Init ---
for key in ["question_index", "questions", "user_answers", "feedback", "scores", "user_details", "ready"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key in ["questions", "user_answers", "feedback", "scores"] else {} if key == "user_details" else False

# --- Helpers ---
def extract_text_from_pdf(uploaded_file):
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        return " ".join(page.get_text() for page in doc)

def clean_questions(raw_qs):
    cleaned = []
    for q in raw_qs:
        q = q.strip()
        q = re.sub(r"^[\-\•\d\.\)\s]+", "", q)
        if len(q) > 5:
            cleaned.append(q.strip())
    return cleaned

def generate_questions(api_key, role, resume_text):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    role_prompt = f"Generate 5 interview questions for the role: {role}."
    resume_prompt = f"Resume:\n{resume_text[:3000]}\n\nGenerate 5 interview questions based on this resume."

    role_response = model.generate_content(role_prompt).text
    resume_response = model.generate_content(resume_prompt).text

    role_qs = clean_questions(role_response.split("\n"))
    resume_qs = clean_questions(resume_response.split("\n"))
    return (role_qs + resume_qs)[:10]

def evaluate_answers(api_key, questions, answers):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    feedback_list = []
    score_list = []
    for q, a in zip(questions, answers):
        prompt = (
            f"Evaluate the candidate's answer:\n\n"
            f"Question: {q}\nAnswer: {a}\n\n"
            f"Provide feedback and a score out of 10. Format:\n"
            f"Feedback: <feedback>\nScore: <score>/10"
        )
        response = model.generate_content(prompt).text
        feedback = re.search(r"Feedback:\s*(.*)", response)
        score = re.search(r"Score:\s*(\d+)", response)

        fb = feedback.group(1).strip() if feedback else "No feedback provided."
        sc = int(score.group(1)) if score else 0
        feedback_list.append(fb)
        score_list.append(sc)

    return feedback_list, score_list

def download_csv():
    data = {
        "Question": st.session_state.questions,
        "Answer": st.session_state.user_answers,
        "Feedback": st.session_state.feedback,
        "Score": st.session_state.scores
    }
    df = pd.DataFrame(data)
    return df.to_csv(index=False).encode("utf-8")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("📥 Candidate Info")
    name = st.text_input("👤 Name")
    email = st.text_input("📧 Email")
    experience = st.selectbox("💼 Experience", ["Fresher", "1-3 years", "3-5 years", "5+ years"])
    api_key = st.text_input("🔐 Gemini API Key", type="password")

    job_role = st.selectbox("📌 Role", ["Software Engineer", "Data Scientist", "Product Manager", "Custom..."])
    custom_role = st.text_input("✏️ Custom Role") if job_role == "Custom..." else ""
    role = custom_role if custom_role else job_role
    resume_file = st.file_uploader("📄 Upload Resume (PDF)", type=["pdf"])

    if st.button("🚀 Generate Questions"):
        if all([name, email, experience, api_key, role, resume_file]):
            with st.spinner("Generating questions..."):
                resume_text = extract_text_from_pdf(resume_file)
                questions = generate_questions(api_key, role, resume_text)

                st.session_state.questions = questions
                st.session_state.question_index = 0
                st.session_state.user_answers = [""] * len(questions)
                st.session_state.user_details = {
                    "Name": name,
                    "Email": email,
                    "Experience": experience,
                    "Role Applied": role,
                }
                st.session_state.ready = True
                st.session_state.feedback = []
                st.session_state.scores = []
                st.success("✅ Questions ready! Switch to Interview tab.")
        else:
            st.warning("⚠️ Please complete all fields and upload a resume.")

# --- Main Body ---
if st.session_state.ready:
    tab1, tab2 = st.tabs(["🧑‍💻 Interview", "📊 Results"])

    with tab1:
        idx = st.session_state.question_index
        total_qs = len(st.session_state.questions)

        st.progress((idx) / total_qs, text=f"{idx}/{total_qs} questions answered")

        if idx < total_qs:
            st.markdown(f"### ✅ Question {idx+1}")
            st.markdown(f"**{st.session_state.questions[idx]}**")
            answer = st.text_area("✍️ Your Answer:", value=st.session_state.user_answers[idx], key=f"answer_{idx}")

            if st.button("Next ➡️", key=f"next_{idx}"):
                if answer.strip():
                    st.session_state.user_answers[idx] = answer.strip()
                    st.session_state.question_index += 1
                    st.rerun()
                else:
                    st.warning("❗Please enter your answer before continuing.")
        else:
            st.success("✅ All answers submitted. Switch to '📊 Results' tab for feedback.")

    with tab2:
        if not st.session_state.feedback and st.session_state.user_answers.count("") == 0:
            with st.spinner("Evaluating your answers..."):
                fb, sc = evaluate_answers(api_key, st.session_state.questions, st.session_state.user_answers)
                st.session_state.feedback = fb
                st.session_state.scores = sc

        if st.session_state.feedback:
            st.markdown("## 🧾 Interview Summary")
            for key, val in st.session_state.user_details.items():
                st.markdown(f"**{key}:** {val}")

            total = sum(st.session_state.scores)
            avg = total / len(st.session_state.questions)
            st.markdown(f"### 📊 Final Score: `{total} / 100`")
            st.markdown(f"📈 **Average Score:** `{avg:.1f} / 10`")

            st.progress(avg / 10, text=f"{avg:.1f}/10 average score")

            st.markdown("### 📋 Feedback per Question")
            for i, q in enumerate(st.session_state.questions):
                st.markdown(f"**Q{i+1}: {q}**")
                st.markdown(f"- ✍️ Answer: {st.session_state.user_answers[i]}")
                st.markdown(f"- 💬 Feedback: {st.session_state.feedback[i]}")
                st.markdown(f"- 🏅 Score: {st.session_state.scores[i]}/10")
                st.markdown("---")

            # --- Download CSV Button ---
            csv = download_csv()
            st.download_button("📥 Download Results (CSV)", data=csv, file_name="interview_results.csv", mime="text/csv")

            if st.button("🔁 Restart Interview"):
                for key in ["question_index", "questions", "user_answers", "feedback", "scores", "user_details", "ready"]:
                    st.session_state[key] = [] if key in ["questions", "user_answers", "feedback", "scores"] else {} if key == "user_details" else False
                st.rerun()
