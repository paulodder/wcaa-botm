import pandas as pd
from string import ascii_lowercase
import typeform
import json
import re
import base64
from pathlib import Path
import datetime
import requests
import dotenv

DOTENV_KEY2VAL = dotenv.dotenv_values()
TOKEN = DOTENV_KEY2VAL["TOKEN"]


inv_series = lambda s: pd.Series(data=s.index.values, index=s.values)
get_date = lambda txt: re.findall("[\d]{4}-[\d]{2}-[\d]{2}", txt)[0]
get_timestamp = lambda txt: "_".join(
    [
        re.findall("[\d]{4}-[\d]{2}-[\d]{2}", txt)[0],
        re.findall("[\d]{2}.[\d]{2}.[\d]{2}", txt)[1],
    ]
)


class FormCreator:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.tf = typeform.Typeform(TOKEN)
        self.image_list = json.loads(
            requests.get(
                "https://api.typeform.com/images",
                headers={"Authorization": f"Bearer {TOKEN}"},
            ).content
        )

    def get_fname2date_for(self, month):
        fname2date_obj = dict()
        for fname in os.listdir(self.data_dir):
            if not fname.startswith("WhatsApp Image"):
                continue
            date_str = get_date(fname)
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            fname2date_obj[fname] = date_obj
        fname2date_obj = pd.Series(fname2date_obj)
        fname2date_obj.sort_values(ascending=True, inplace=True)
        fname2date_obj_month = fname2date_obj[
            fname2date_obj.apply(lambda dt: dt.month == month)
        ]
        return fname2date_obj_month

    def _get_imageid2remote_id(self, date2fnames):
        imageid2remote_id = dict()
        for date, fnames in date2fnames.iteritems():
            print(date)
            for fname, suffix in zip(
                sorted(fnames, key=self._get_imageid), ascii_lowercase
            ):
                imageid = f"{get_date(fname)}-{suffix}"
                remote_id = self._get_remote_id(fname, imageid)
                imageid2remote_id[imageid] = remote_id
        return pd.Series(imageid2remote_id).sort_values()

    def _upload_image(self, fname):
        fpath = str(self.data_dir / fname)
        img = self._read_image(fname)
        base64.b64encode(img)

    def _read_image(self, fname):
        with open(fname, "rb") as f:
            b64 = base64.b64encode(f.read())
        return b64

    def _get_imageid(self, fname):
        timestamp = get_timestamp(fname)
        second_part_of_id = re.findall("\([\d]\)", fname)
        if second_part_of_id:
            second_part_of_id = f"_{second_part_of_id[0][1]}"
        else:
            second_part_of_id = "_0"
        return timestamp + second_part_of_id

    def make_form_month(self, month):
        fname2date = self.get_fname2date_for(month)
        date2fname = inv_series(fname2date)
        date2fnames = (
            date2fname.groupby(level=0)
            .agg(lambda s: sorted(s, key=get_date))
            .sort_values()
        )
        imageid2remote_id = self._get_imageid2remote_id(date2fnames)
        self.imageid2remote_id = imageid2remote_id
        j = self._make_form_json(imageid2remote_id)
        json_response = fc.tf.forms.create(j)
        return json_response["_links"]["display"]

    def _get_remote_id(self, fname, imageid):
        for image_dict in self.image_list:
            if image_dict["file_name"] == f"{imageid}.png":
                return image_dict["id"]
        b64_str = self._read_image(self.data_dir / fname)
        r = requests.post(
            "https://api.typeform.com/images",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={
                "file_name": f"{imageid}.png",
                "image": b64_str.decode("utf-8"),
            },
        )
        json_info = json.loads(r.content)
        self.image_list.append(json_info)
        return json_info["id"]

    def _make_choices_json(self, imageid2file_id):
        out = []
        for i, (imageid, file_id) in enumerate(
            imageid2file_id.sort_index().iteritems()
        ):
            out.append(
                {
                    "ref": f"choice_ref{i}",
                    "label": imageid,
                    "attachment": {
                        "type": "image",
                        "href": f"https://images.typeform.com/images/{file_id}",
                    },
                }
            )
        return out

    def _make_form_json(self, imageid2remote_id):
        month_name = (
            (datetime.datetime.now() - datetime.timedelta(days=28))
            .strftime("%B")
            .lower()
        )
        with open("typeform_template.json", "r") as f:
            default_json = json.load(f)
        all_choices_json = self._make_choices_json(imageid2remote_id)
        fields_json = {
            "title": f"we care about air BotM ({month_name})\n\nwhich 3 pictures do you like most? (we know it says choose as many as you like but please don't and choose at most 3)",
            "ref": "only_question_that_matters",
            "properties": {
                "randomize": False,
                "allow_multiple_selection": True,
                "allow_other_choice": False,
                "supersized": False,
                "show_labels": True,
                "choices": all_choices_json,
            },
            "validations": {"required": False},
            "type": "picture_choice",
        }
        default_json["fields"].append(fields_json)
        default_json["title"] = f"we care about air BotM ({month_name})"
        return default_json


# # Create form for given month
# fc = FormCreator("data/")
# form_link = fc.make_form_month(6)
# print(form_link)
