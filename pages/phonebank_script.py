from cryptography.fernet import Fernet, InvalidToken
import pandas as pd
import streamlit as st
import yaml


def main():
    st.write("# Phone Banking")
    cred_form = st.form("credentials")
    your_name = cred_form.text_input("your name")
    password = cred_form.text_input(
        "Please enter the key required to unlock the phone banking script"
    ).encode("utf-8")
    cred_form.form_submit_button("submit")
    if password == "":
        return

    rep_df = pd.read_csv("data/reps.csv").set_index("district")
    house_district = st.number_input(
        "callee house district", value=None, step=1,
        min_value=1,
        max_value=151
    )
    if house_district is None:
        return

    rep_name = rep_df.loc[house_district]["rep"]
    rep_phone = rep_df.loc[house_district]["number"]

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

    script = yaml.load(decrypted_text, yaml.SafeLoader)
    steps_by_name = {
        step["name"]: step for step in script["steps"]
    }

    if "step_history" not in st.session_state.keys():
        st.session_state["step_history"] = {script["starting_point"]: None}

    step_name = script["starting_point"]
    while True:
        step = steps_by_name[step_name]
        if "title" in step.keys():
            st.write(f"# {step['title']}")

        st.markdown(step["text"].format(
            your_name=your_name,
            rep_phone_number=rep_phone,
            rep_name=rep_name
        ))
        if "yes_response" in step.keys():
            response_for_step = st.checkbox(
                "Check if they say yes", key=f"{step_name}-response")

            if response_for_step:
                st.session_state["step_history"][step_name] = step["yes_response"]
            else:
                st.session_state["step_history"][step_name] = None

        step_name = st.session_state["step_history"].get(step_name)
        if step_name is None:
            break


if __name__ == "__main__":
    main()
