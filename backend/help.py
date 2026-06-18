from werkzeug.security import generate_password_hash

my_password = "password456"


# MUST match exactly what you put in your .env file
pepper = "s0m3_v3ry_l0ng_and_c0mpl3x_s3cr3t_str1ng_n0b0dy_kn0ws!" 

# Combine and hash
peppered_password = my_password + pepper
hashed_password = generate_password_hash(peppered_password)

print("\n--- COPY THIS SECURE HASH FOR YOUR DATABASE ---")
print(hashed_password)
print("-----------------------------------------------\n")