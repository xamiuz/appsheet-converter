import streamlit as st
import json
import pandas as pd
import io

st.set_page_config(page_title="AppSheet JSON to XLSX Converter", layout="wide")

st.title("AppSheet JSON to Excel Converter")
st.write("tolong upload json appsheet anda menjadi untuk melihat data tabel nya")

uploaded_file = st.file_uploader("Choose a JSON file", type="json")

if uploaded_file is not None:
    # Try different encodings
    data = None
    bytes_data = uploaded_file.getvalue()
    
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    for encoding in encodings:
        try:
            string_data = bytes_data.decode(encoding)
            data = json.loads(string_data)
            st.success(f"Successfully loaded JSON with encoding: {encoding}")
            break
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as e:
            st.error(f"JSON Decode Error with {encoding}: {e}")
            break
            
    if data:
        tables = []
        # Try finding tables in different locations
        if 'Template' in data and 'Tables' in data['Template']:
            tables = data['Template']['Tables']
        elif 'Template' in data and 'AppData' in data['Template'] and 'DataSets' in data['Template']['AppData']:
            tables = data['Template']['AppData']['DataSets']
        
        if tables:
            st.write(f"Found {len(tables)} tables/datasets.")
            
            # Extract data
            table_list = []
            for table in tables:
                table_info = {
                    "Table Name": table.get("Name", ""),
                    "Description": table.get("Description", "") or table.get("Comment", ""), # Fallback to Comment
                    "Type": table.get("TableType", "") or table.get("Type", "") or "Data Table",
                    "Schema Name": table.get("Schema", "") or table.get("SchemaName", ""),
                    "Source": table.get("Source", ""),
                    "SourcePath": table.get("SourcePath", ""),
                    "UpdateMode": table.get("UpdateMode", ""),
                    "AllowedUpdates": str(table.get("AllowedUpdates", "")),
                    "ReadOnly": table.get("ReadOnly", False)
                }
                table_list.append(table_info)
            
            # Create DataFrame for Tables
            df_tables = pd.DataFrame(table_list)
            
            # Show preview
            st.subheader("Preview Extracted Data")
            st.dataframe(df_tables)
            
            # Convert to Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Main sheet named 'Tables Overview' as per screenshot
                df_tables.to_excel(writer, index=False, sheet_name='Tables Overview')
                
                # Extract Schemas
                if 'Template' in data and 'AppData' in data['Template'] and 'DataSchemas' in data['Template']['AppData']:
                    schemas = data['Template']['AppData']['DataSchemas']
                    st.write(f"Found {len(schemas)} schemas.") # Debug info
                    
                    # Create a dictionary for quick lookup
                    schema_dict = {schema['Name']: schema for schema in schemas}
                    
                    sheets_created = 0
                    for table in table_list:
                        # Use schema lookup
                        schema_name = table.get("Schema Name")
                        if schema_name:
                             if schema_name in schema_dict:
                                schema_data = schema_dict[schema_name]
                                # Found that columns are in 'Attributes', not 'Columns'
                                if 'Attributes' in schema_data:
                                    columns = schema_data['Attributes']
                                    
                                    # Process columns to get specific User Requested fields
                                    processed_columns = []
                                    for col in columns:
                                        # Parse TypeAuxData for specific formulas
                                        aux_data = {}
                                        if col.get('TypeAuxData'):
                                            try:
                                                aux_data = json.loads(col['TypeAuxData'])
                                            except:
                                                pass
                                        
                                        # Map fields
                                        col_data = {
                                            "Column Name": col.get("Name", ""),
                                            "Show": aux_data.get("Show_If") if aux_data.get("Show_If") else ("" if not col.get("IsHidden") else "FALSE"),
                                            "Type": col.get("Type", ""),
                                            "Valid If": aux_data.get("Valid_If", ""),
                                            "Require": aux_data.get("Required_If") if aux_data.get("Required_If") else ("TRUE" if col.get("IsRequired") else ""),
                                            "App Formula": col.get("AppFormula", ""),
                                            "Initial Value": col.get("Default") or col.get("DefaultExpression") or "",
                                            "Spreadsheet Formula": col.get("Formula", ""),
                                            "Key": col.get("IsKey", False),
                                            "Editable": aux_data.get("Editable_If") if aux_data.get("Editable_If") else ("" if col.get("DefEdit", True) else "FALSE"),
                                            "Label": col.get("IsLabel", False)
                                        }
                                        processed_columns.append(col_data)

                                    # Create Schema DataFrame
                                    df_schema = pd.DataFrame(processed_columns)
                                    
                                    # Sanitize sheet name (max 31 chars, no invalid chars)
                                    # User requested simple table names as sheet names (e.g. "Control", "HASIL")
                                    raw_sheet_name = table['Table Name']
                                    sheet_name = raw_sheet_name[:30].replace("/", "_").replace("\\", "_").replace("?", "")
                                    
                                    # Handle duplicate sheet names if any (unlikely for table names but good practice)
                                    try:
                                        df_schema.to_excel(writer, index=False, sheet_name=sheet_name)
                                        sheets_created += 1
                                    except ValueError:
                                         st.warning(f"Skipped duplicate or invalid sheet name: {sheet_name}")
                                else:
                                    st.warning(f"Schema '{schema_name}' has no columns (key 'Attributes' missing).")
                             else:
                                 # Try stripping suffix if exact match fails, sometimes schema names differ slightly
                                 st.warning(f"Schema '{schema_name}' not found in DataSchemas.")
                        else:
                             st.warning(f"Table '{table['Table Name']}' has no Schema Name.")
                    
                    st.success(f"Created {sheets_created} extra sheets.")

            excel_data = output.getvalue()
            
            # Download button
            st.download_button(
                label="Download Excel File",
                data=excel_data,
                file_name="converted_tables.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        else:
            st.error("Could not find table definitions. Expected 'Template -> Tables' or 'Template -> AppData -> DataSets'.")
    else:
        st.error("Failed to decode file with standard encodings (utf-8, latin-1).")
