from dotenv import load_dotenv
load_dotenv()

from langchain.chains import LLMChain
from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import os
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
import sys
from time import sleep

# for text extraction
llm = ChatOpenAI(model="gpt-4-0125-preview")
# for image extraction
lmm = ChatVertexAI(model_name="gemini-1.0-pro-vision")

page_info_extraction_prompt_template = PromptTemplate.from_template("""Given the input text below, delimited by dashes, extract the key information from this text following these guidelines.

Analyze the information conveyed in the input text and summarize the ideas, themes, and facts presented. Focus on understanding the overall message and informational content, Structure your output to follow this formatting:

1. Main Ideas:
   - Identify and describe the primary themes or ideas presented in the document. Highlight any unique themes or ideas that are present in the input text.

2. Facts and Data:
   - Extract any factual information, data, or statistics mentioned in the input text.
------------------------------------------------------------------------------------------------------------------------
{input_text}""")

summaries_comparison_prompt_template = PromptTemplate.from_template("""You are going to be given two texts, separated by a line of stars.
Both texts are in the same formatting.
Your job is to list the differences in information provided in the two texts follwing this formatting:
                                                                    
1. Different Information:
   - Identify and describe the different themes or ideas presented in the two documents. Highlight any unique themes or ideas that are present in one text and not the other.

2. Different Facts and Data:
   - Extract any factual information, data, or statistics mentioned in one text and not the other.

Here are the two texts, delimited with lines of dashes:
------------------------------------------------------------------------------------------------------------------------
{doc1}
********************************************************************************************************************
{doc2}
------------------------------------------------------------------------------------------------------------------------
If there are no differences, please output the format as is, with no content. No need to add bullet points or explanations.""")

# using the prompt from https://python.langchain.com/docs/use_cases/summarization#option-3.-refine
final_summary_prompt_template = PromptTemplate.from_template("""Your job is to produce a final summary.
We have provided an existing summary up to a certain point, here it is delimited by dashes:
------------------------------------------------------------------------------------------------------------------------
{existing_summary}
------------------------------------------------------------------------------------------------------------------------
We have the opportunity to refine the existing summary (only if needed) with some more context below, delimited by stars:
********************************************************************************************************************
{additional_context}
********************************************************************************************************************
Given the new context, refine the original summary. If the context isn't useful, return the original summary.""")

def summarize_pdf_page(doc_path: str, page_num: int):
    extraction_summary = ""
    with open(doc_path, 'rb') as file:
        reader = PdfReader(file)
        input_text = ''
        # looping over each page
        input_text = reader.pages[page_num].extract_text()
        # extracting page contents from a multimodal model if empty
        if input_text.strip() == "":
            page_2_image_extract = convert_from_path(doc_path, first_page=page_num+1, last_page=page_num+1)
            image_output_path = "tmp.jpg"
            page_2_image_extract[0].save(image_output_path)
            image_message = {
                "type": "image_url",
                "image_url": {"url": "tmp.jpg"},
            }
            text_message = {
                "type": "text",
                "text": "extract the text from this image and output it as is, no pre-ambles or explanations, just the text as is",
            }
            message = HumanMessage(content=[text_message, image_message])
            output = lmm([message])
            input_text = output.content
            # delete temporary image file
            os.remove(image_output_path)
        page_extraction_chain = LLMChain(llm=llm, prompt=page_info_extraction_prompt_template)
        extraction_summary = page_extraction_chain.run(input_text=input_text)
        return extraction_summary

# check if there are two command line arguments
if len(sys.argv) != 3:
    print("Usage: python app.py <doc1_path> <doc2_path>")
    sys.exit(1)

# get the documents paths from the command line
doc1_path = sys.argv[1]
doc2_path = sys.argv[2]

def make_summary_chunks(doc1: str, doc2: str):
    # create `doc1.md` and `doc2.md` summary files
    doc1_md_path = "doc1.md"
    doc2_md_path = "doc2.md"
    os.system(f"touch {doc1_md_path}")
    os.system(f"touch {doc2_md_path}")
    doc_summary_path = "doc_summary.md"
    os.system(f"touch {doc_summary_path}")

    num_pages_doc1 = 0
    num_pages_doc2 = 0
    both_num_pages = 0

    with open(doc1, 'rb') as file:
        reader = PdfReader(file)
        num_pages_doc1 = len(reader.pages)
    with open(doc1, 'rb') as file:
        reader = PdfReader(file)
        num_pages_doc2 = len(reader.pages)

    # the number of pages to summarize (the minimum number of pages between the two documents)
    if num_pages_doc1 > num_pages_doc2:
        both_num_pages = num_pages_doc2
    else:
        both_num_pages = num_pages_doc1

    # looping over each page
    for i in range(both_num_pages):
        # write the summary to the file
        with open(doc1_md_path, 'a') as file:
            file.write(summarize_pdf_page(doc1, i))
        with open(doc2_md_path, 'a') as file:
            file.write(summarize_pdf_page(doc2, i))
        doc1_content = ""
        doc2_content = ""
        # getting the contents of the files
        with open(doc1_md_path, 'r') as file:
            doc1_content = file.read()
        with open(doc2_md_path, 'r') as file:
            doc2_content = file.read()
        comparison_chain = LLMChain(llm=llm, prompt=summaries_comparison_prompt_template)
        comparison_summary_chunk = comparison_chain.run(doc1=doc1_content, doc2=doc2_content)
        # write the summary to the file
        with open(doc_summary_path, 'a') as file:
            file.write(comparison_summary_chunk)
            file.write("\n------------------------------------------------------------------------------------------------------------------------\n")
        # clearing the contents of the docs files
        with open(doc1_md_path, 'w') as file:
            file.write("")
        with open(doc2_md_path, 'w') as file:
            file.write("")
        # sleep for 1 second for VertexAI and OpenAI APIs rate limiting
        sleep(1)

    # delete `doc1.md` and `doc2.md` summary files
    os.remove(doc1_md_path)
    os.remove(doc2_md_path)

# ! uncomment if your summary is not ready
# make_summary_chunks(doc1_path, doc2_path)

final_summary = ""
tmp_summary = ""

# load the summary doc
with open("doc_summary.md", 'r') as file:
    tmp_summary = file.read()

# split the summary into chunks using the dashes delimiter
chunks = tmp_summary.split("------------------------------------------------------------------------------------------------------------------------")

for chunk in chunks:
    final_summary_chain = LLMChain(llm=llm, prompt=final_summary_prompt_template)
    final_summary += final_summary_chain.run(existing_summary=final_summary, additional_context=chunk)
    sleep(1)

# write the final summary to a file
with open("doc_final_summary.md", 'w') as file:
    file.write(final_summary)