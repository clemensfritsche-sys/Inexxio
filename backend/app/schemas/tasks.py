"""Aufgaben – was die Oberfläche bekommt (``services/tasks.view``)."""

from typing import Optional

from pydantic import BaseModel


class TaskMark(BaseModel):
    """►► **Eine Aufgabe, wie man sie sieht** – kein Satz: was zu tun ist, zeigt die Stelle. ◄◄"""
    key: str
    #: Der Datensatz, an dem sie steht.
    object_id: int
    #: Die Stelle darin (``data-todo``): ein Abschnitt oder ``step:<id>``.
    part: str
    #: Meine Aufgabe (die eine, die zuoberst steht).
    mine: bool = False
    #: Niemand, der da ist, kann sie – das «!» für alle.
    orphan: bool = False


class TasksOut(BaseModel):
    """►►► **Was eine Person sieht** – ihre eine Aufgabe und die roten Zeichen (die eigene, beim
    Admin alle, bei allen die verwaisten). ◄◄◄"""
    mine: Optional[TaskMark] = None
    visible: list[TaskMark]
