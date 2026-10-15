from cloudflare_ai import run_ai


def main():
    messages = [
        {
            "role": "user",
            "content": "Reply with exactly: Tango AI works."
        }
    ]

    result = run_ai(messages)

    answer = result["choices"][0]["message"]["content"]

    print("Cloudflare AI response:")
    print(answer.strip())


if __name__ == "__main__":
    main()
