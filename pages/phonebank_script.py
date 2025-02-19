from cryptography.fernet import Fernet, InvalidToken
import pandas as pd
import streamlit as st
import yaml


def initialize_state(starting_point: str):
    if "step_history" not in st.session_state.keys():
        st.session_state["step_history"] = {starting_point: None}

def reset_history(starting_point: str):
    st.session_state["step_history"] = {starting_point: None}
    st.session_state["callee_name"] = None
    st.session_state["callee_house_district"] = None


def main():
    st.write("# Phone Banking")
    cred_form = st.form("credentials")
    your_name = cred_form.text_input("your name")
    your_chapter = cred_form.text_input("your chapter", value="Austin DSA")
    if "dsa" not in your_chapter.lower():
       your_chapter = f"{your_chapter} DSA"
    password = cred_form.text_input(
        "Please enter the key required to unlock the phone banking script"
    ).encode("utf-8")
    cred_form.form_submit_button("submit")
    try:
        cipher_suite = Fernet(password)
    except ValueError:
        return

    with open("data/phonebank_scripts/2025_02_11_central_tx_script_encrypted.txt", 'rb') as fh:
        cipher_text = fh.read()

    try:
        decrypted_text = cipher_suite.decrypt(cipher_text).decode("utf-8")
    except InvalidToken:
        st.write("Wrong password provided. Please try again")
        return

    step_0_form = st.form("step-0-form")
    callee_name = step_0_form.text_input(
        "Enter the name of the person you're calling", key="callee_name"
    )
    rep_df = pd.read_csv("data/reps.csv").set_index("district")
    house_district = step_0_form.number_input(
        "callee house district", value=None, step=1,
        min_value=1,
        max_value=151,
        key="callee_house_district"
    )
    step_0_form.form_submit_button("enter")
    if house_district is None:
        return

    rep_name = rep_df.loc[house_district]["rep"]
    rep_phone = rep_df.loc[house_district]["number"]

    script = yaml.load(decrypted_text, yaml.BaseLoader)
    steps_by_name = {
        step["name"]: step for step in script["steps"]
    }

    initialize_state(script["starting_point"])

    step_name = script["starting_point"]
    while True:
        if step_name == "end_and_recycle":
            st.write("Script ended. Please click the button below "
                     "to reset the script for the next call")
            st.button("reset script", on_click=lambda: reset_history(script["starting_point"]))
            break
        else:
            step = steps_by_name[step_name]
            st.markdown(step["text"].format(
                your_name=your_name,
                your_chapter=your_chapter,
                house_district=house_district,
                callee_name=callee_name,
                rep_phone_number=rep_phone,
                rep_name=rep_name
            ))

            if "responses" in step.keys():
                next_step_label = st.selectbox(
                    "select response",
                    list(step["responses"].keys()),
                    index=None,
                    key=f"{step_name}-response"
                )
                next_step = step["responses"].get(next_step_label)
                st.session_state["step_history"][step_name] = next_step

            step_name = st.session_state["step_history"].get(step_name)
            if step_name is None:
                break


if __name__ == "__main__":
    main()
